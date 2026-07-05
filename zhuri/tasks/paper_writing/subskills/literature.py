"""Literature Survey sub-skill (§11.1 #1) with EC4 verification cadence.

EC4: citation-like content MUST be verified **every 20 entries**, never batched
to the end. :func:`verification_points` returns the indices at which verification
fires; :func:`run_survey` interleaves verification into collection.

The :class:`LiteratureSurveySkill` class encodes the full upstream 4-stage
pipeline (Recall → LQS → Classify → Upgrade) as a prompt template.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from zhuri.agents.prompt import WorkPrompt, build_prompt
from zhuri.tasks.base import SubSkill, SubSkillContext

VERIFY_EVERY = 20


def verification_points(total: int, *, every: int = VERIFY_EVERY) -> list[int]:
    """Indices (1-based counts) at which a verification pass must fire."""
    return [i for i in range(every, total + 1, every)]


@dataclass
class SurveyResult:
    collected: int
    verified: int
    verification_rounds: list[int] = field(default_factory=list)
    hallucinated: int = 0


def run_survey(citations: list[dict], *, verify) -> SurveyResult:
    """Collect citations, verifying every 20 (EC4).

    ``verify(batch)`` returns the count of hallucinated/invalid entries in the
    batch; those are dropped. Verification fires *during* collection.
    """
    verified = 0
    hallucinated = 0
    rounds: list[int] = []
    batch: list[dict] = []
    kept = 0
    for idx, cite in enumerate(citations, start=1):
        batch.append(cite)
        kept += 1
        if idx % VERIFY_EVERY == 0:
            bad = verify(batch)
            verified += len(batch)
            hallucinated += bad
            kept -= bad
            rounds.append(idx)
            batch = []
    if batch:  # final partial batch still verified, not skipped
        bad = verify(batch)
        verified += len(batch)
        hallucinated += bad
        kept -= bad
    return SurveyResult(
        collected=kept,
        verified=verified,
        verification_rounds=rounds,
        hallucinated=hallucinated,
    )


# ---------------------------------------------------------------------------
# LiteratureSurveySkill — prompt-builder for the work agent
# ---------------------------------------------------------------------------

class LiteratureSurveySkill(SubSkill):
    name = "literature"
    description = (
        "4-stage literature pipeline: Recall → LQS Scoring → "
        "A/B/C/D Classification → Venue Upgrade"
    )

    def build_prompt(self, ctx: SubSkillContext) -> WorkPrompt:
        return build_prompt(
            background=ctx.task_spec[:3000] or "Conduct a systematic literature survey.",
            deliverable=LITERATURE_DELIVERABLE,
            working_dir=ctx.extra or ".",
            caps=LITERATURE_CAPS,
            completion_criteria=LITERATURE_COMPLETION,
            directions_tried=ctx.directions_tried,
            extra=self._findings_extra(ctx),
        )

    @staticmethod
    def _findings_extra(ctx: SubSkillContext) -> str:
        if not ctx.findings:
            return ""
        recent = ctx.findings[-10:]
        return (
            "# Prior literature findings (last 10)\n"
            + "\n".join(f"- {f.claim} :: {f.evidence}" for f in recent)
        )


# ---------------------------------------------------------------------------
# Prompt fragments — the detailed upstream workflow
# ---------------------------------------------------------------------------

LITERATURE_DELIVERABLE = """Produce a systematic literature survey with the following outputs:

## Output files (write to the working directory)
1. `references.bib` — BibTeX entries for all classified citations
2. `citation_plan.jsonl` — one JSON line per cited work:
   {"key":"...", "class":"A|B|C|D", "lqs":7.5, "depth":"1-3 paragraphs"|"2-5 sentences"|"1 sentence", "venue_status":"accepted"|"arxiv", "verified":true}
3. `literature_report.md` — summary with statistics (total candidates, A/B/C/D counts, LQS distribution, arXiv-only%, year distribution)

## Required workflow (execute in order)

### Stage 1: High-Recall Retrieval
- Generate 20-30 keyword queries covering different taxonomy dimensions of the topic
- Each taxonomy cell needs 3+ query variants (core terms, synonyms, method names)
- Search strategy: academic databases (arXiv, DBLP, Semantic Scholar, Google Scholar)
- Snowball: from 3-5 seed papers, follow citation graphs bidirectionally
- Target: collect 200-500 raw candidates

### Stage 2: LQS Multi-Dimensional Scoring
Score every candidate on 5 dimensions:

| Dimension      | Weight | Scoring Rule                                    |
|----------------|--------|-------------------------------------------------|
| Recency        | 30%    | ≤6 months=10, ≤1 year=8, ≤2 years=5, ≤3 years=3 |
| Citation Impact| 25%    | cites/month: ≥50=10, ≥10=8, ≥3=6, ≥1=4, <1=2   |
| Venue          | 20%    | Top-tier(ICLR/NeurIPS/ICML/ACL)=10, Strong=7, Workshop=4, arXiv only=2 |
| Institution    | 10%    | Top lab(FAIR/DeepMind/OpenAI)=10, Top-10 univ=9, Other univ=6, Unknown=3 |
| Acceptance     | 15%    | Published/accepted=10, Under review=5, Preprint only=3 |

Classification thresholds:
- LQS ≥ 7.0  → MUST-CITE (A or B level)
- LQS 5.0–7.0 → CONDITIONAL (B or C level)
- LQS < 5.0  → DROP (record reason)

### Stage 3: Citation Depth Classification
- **A-level** (3-5 per chapter): 1-3 paragraphs of discussion. Section protagonist.
- **B-level** (5-10 per chapter): 2-5 sentences. Important supporting insight.
- **C-level** (as needed): 1 sentence. Supporting evidence or background.
- **D-level**: dropped — do NOT include in references.bib.

### Stage 4: Venue Upgrade
- Cross-check every arXiv-only entry against DBLP and OpenReview
- If found with "Accepted at X" status → upgrade to @inproceedings with correct venue
- Target: arXiv-only ratio ≤ 60% of total references

## Verification (EC4 — mandatory, every 20 citations)
- After every 20 citations: verify title, first-author last name, year, venue against source
- Target: verification rate ≥ 80%, hallucinated citations = 0
- Year distribution: within-last-12-months ≥ 40%, accepted/published ≥ 30%
- NEVER invent a paper title, DOI, or author name. Mark unverifiable entries as DROPPED.
"""

LITERATURE_CAPS = (
    "Working directory: search cache + references.bib + citation_plan.jsonl. "
    "Each output file ≤ 300 lines (EC1). Max 15 LLM rounds or 30 min."
)

LITERATURE_COMPLETION = (
    "Task is complete when: (1) ≥ 80 citations in references.bib, "
    "(2) citation_plan.jsonl has A/B/C/D classification for every entry, "
    "(3) ≥ 80% of entries pass verification with 0 hallucinated, "
    "(4) arXiv-only ≤ 60%, within-1-year ≥ 40%, accepted ≥ 30%, "
    "(5) literature_report.md written with full statistics. "
    "Emit FINDING: <claim> :: <evidence> for each major discovery. "
    "Say DONE when all stages complete."
)
