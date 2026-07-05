"""Peer Review Simulation sub-skill (§11.1 #5, §11.5 anti-inflation).

3–5 reviewer personas score independently; the final score is the **median**.
Anti-inflation rules cap the first round at 7.0, allow at most +1.5 per round,
require ≥1 unresolved weakness to remain, and require ≥1 reviewer per round to use
a different model (ties to §10.5 per-round model diversity).

:class:`PeerReviewSkill` encodes all 5 reviewer personas, the scoring protocol,
and anti-inflation rules as a prompt template for the review agent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from zhuri.agents.prompt import WorkPrompt, build_prompt
from zhuri.tasks.base import SubSkill, SubSkillContext

FIRST_ROUND_CAP = 7.0
MAX_DELTA_PER_ROUND = 1.5


@dataclass
class ReviewOutcome:
    final_score: float
    raw_median: float
    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def review_round(
    *,
    round_index: int,
    reviewer_scores: list[float],
    reviewer_models: list[str],
    prev_final: float | None,
    unresolved_weaknesses: list[str],
) -> ReviewOutcome:
    """Compute an anti-inflation-adjusted final score for one review round."""
    if not (3 <= len(reviewer_scores) <= 5):
        raise ValueError("require 3–5 reviewers (§11.1)")
    if len(reviewer_models) != len(reviewer_scores):
        raise ValueError("reviewer_models must align with reviewer_scores")

    violations: list[str] = []
    raw = float(median(reviewer_scores))
    final = raw

    # First-round cap.
    if round_index == 0 and final > FIRST_ROUND_CAP:
        final = FIRST_ROUND_CAP

    # Max +1.5 per round.
    if prev_final is not None and final - prev_final > MAX_DELTA_PER_ROUND:
        final = prev_final + MAX_DELTA_PER_ROUND

    # ≥1 unresolved weakness must remain.
    if len(unresolved_weaknesses) < 1:
        violations.append("no unresolved weakness remains (anti-inflation)")

    # ≥1 reviewer must use a different model.
    if len(set(reviewer_models)) < 2:
        violations.append("all reviewers used the same model (need ≥1 different)")

    return ReviewOutcome(final_score=round(final, 3), raw_median=raw, violations=violations)


# ---------------------------------------------------------------------------
# PeerReviewSkill — prompt-builder for the review agent
# ---------------------------------------------------------------------------

class PeerReviewSkill(SubSkill):
    name = "review"
    description = (
        "5 reviewer personas → independent scoring (median) → weakness routing. "
        "Anti-inflation: first≤7.0, max+1.5/round, ≥1 unresolved, model diversity."
    )

    def build_prompt(self, ctx: SubSkillContext) -> WorkPrompt:
        return build_prompt(
            background=ctx.task_spec[:3000] or "Simulate peer review of the manuscript.",
            deliverable=REVIEW_DELIVERABLE,
            working_dir=ctx.extra or ".",
            caps=REVIEW_CAPS,
            completion_criteria=REVIEW_COMPLETION,
            directions_tried=ctx.directions_tried,
            extra=self._findings_extra(ctx),
        )

    @staticmethod
    def _findings_extra(ctx: SubSkillContext) -> str:
        if not ctx.findings:
            return ""
        recent = ctx.findings[-15:]
        return (
            "# Manuscript content summary (recent findings)\n"
            + "\n".join(f"- {f.claim} :: {f.evidence}" for f in recent)
        )


REVIEW_DELIVERABLE = """Simulate a rigorous peer review of the compiled manuscript.

## Reviewer Personas (3-5 per round, score independently — no anchoring)

| Persona | Focus | Weight Emphasis |
|---------|-------|----------------|
| R1 Experimentalist | Statistical rigor, baselines, replication, error bars | Experimental validation 30% |
| R2 Theorist | Formal definitions, proofs, MECE taxonomy, taxonomical rigor | Technical depth 35% |
| R3 Perfectionist | Writing quality, figures, formatting, consistency | Clarity 30% |
| R4 Synthesizer | Cross-cutting analysis, gap identification, positioning vs. field | Novelty 25% |
| R5 Newcomer | Accessibility, definitions, examples, "can a PhD student follow?" | Clarity 35% |

## Scoring Dimensions (1-10 each)
1. **Novelty**: New taxonomy? New angle? New experiment? New insight?
2. **Comprehensiveness**: Coverage of the field, citation breadth and depth
3. **Clarity**: Writing quality, figure/table readability, logical flow
4. **Technical Depth**: Formal rigor, critical assessment, non-trivial analysis
5. **Experimental Validation**: Quality and quantity of empirical support

## Scoring Protocol
- Each reviewer scores ALL 5 dimensions independently
- Final score for each reviewer = weighted average of their dimension scores
- Paper final score = **median** of all reviewer scores (NOT mean)
- Calibration reference:
  - 6.0 = Workshop-level (complete but shallow)
  - 7.0 = Main conference (solid contribution)
  - 8.0 = Strong Accept (top 20% of venue)
  - 9.0 = Oral-quality (exceptional)

## Anti-Inflation Rules (MANDATORY)
1. **First-round cap**: maximum score in round 0 is 7.0 (every paper has room to improve)
2. **Max delta**: score can increase at most +1.5 per round
3. **Unresolved weakness**: at least 1 weakness must remain unresolved (perfection is impossible)
4. **Model diversity**: ≥1 reviewer per round MUST use a different LLM model than the others

## Output Format
For EACH round, produce a JSON object:
```json
{
  "round": 0,
  "reviewers": [
    {
      "persona": "R1_Experimentalist",
      "model_used": "deepseek-v4-pro",
      "scores": {"novelty": 7, "comprehensiveness": 8, "clarity": 6, "technical_depth": 7, "experimental": 8},
      "strengths": ["..."],
      "weaknesses": [
        {"severity": "Major", "text": "No error bars on key figure", "route_to": "figures"},
        {"severity": "Minor", "text": "Missing 2025 papers on GRPO", "route_to": "literature"}
      ],
      "recommendation": "Weak Accept"
    }
  ],
  "final_score": 7.0,
  "unresolved_weaknesses": ["No error bars on key figure"]
}
```

## Regression Check
- Before finalizing each round, check: were weaknesses identified in PREVIOUS rounds actually fixed?
- If a previously-fixed weakness has regressed → flag as MAJOR and route immediately
"""

REVIEW_CAPS = (
    "Working directory: review_outcome.json. "
    "3-5 independent reviewer LLM calls. Max 15 LLM rounds or 30 min."
)

REVIEW_COMPLETION = (
    "Task is complete when: (1) 3-5 personas scored all 5 dimensions independently, "
    "(2) final_score = median(reviewer_scores), "
    "(3) all anti-inflation rules checked and satisfied, "
    "(4) each weakness includes a 'route_to' field (literature/structure/experiment/figures), "
    "(5) regression check completed against previous round, "
    "(6) review_outcome.json written. "
    "Emit FINDING: <claim> :: <evidence> for each major review insight. "
    "Say DONE when complete."
)
