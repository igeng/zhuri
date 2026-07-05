"""Paper Structure & Logic sub-skill (§11.1 #2).

Produces a chapter architecture using a MECE taxonomy with hedged formal claims.
Each section file must stay ≤300 lines (EC1).

:class:`PaperStructureSkill` encodes chapter architecture, paragraph logic
patterns, taxonomy design rules, formal claims with hedge ladder, and related
work differentiation as a prompt template.
"""
from __future__ import annotations

from zhuri.agents.prompt import WorkPrompt, build_prompt
from zhuri.tasks.base import SubSkill, SubSkillContext

DEFAULT_SECTIONS = (
    "introduction",
    "related_work",
    "method",
    "experiments",
    "results",
    "discussion",
    "conclusion",
)


def plan_sections(extra: list[str] | None = None) -> list[str]:
    """Return an ordered, MECE section plan."""
    sections = list(DEFAULT_SECTIONS)
    for name in extra or []:
        if name not in sections:
            sections.append(name)
    return sections


def is_mece(sections: list[str]) -> bool:
    """MECE check: no duplicate sections (mutually exclusive)."""
    return len(sections) == len(set(sections))


def hedge_claim(claim: str) -> str:
    """Convert an absolute claim into a hedged, formal one."""
    claim = claim.strip().rstrip(".")
    lowered = claim.lower()
    if lowered.startswith(("we suggest", "our results suggest", "this indicates")):
        return claim + "."
    return f"Our results suggest that {claim[0].lower() + claim[1:]}."


# ---------------------------------------------------------------------------
# PaperStructureSkill — prompt-builder for the work agent
# ---------------------------------------------------------------------------

class PaperStructureSkill(SubSkill):
    name = "structure"
    description = (
        "Chapter architecture + paragraph logic patterns + MECE taxonomy + "
        "hedged formal claims + related work differentiation"
    )

    def build_prompt(self, ctx: SubSkillContext) -> WorkPrompt:
        return build_prompt(
            background=ctx.task_spec[:3000] or "Design the paper structure and logical flow.",
            deliverable=STRUCTURE_DELIVERABLE,
            working_dir=ctx.extra or ".",
            caps=STRUCTURE_CAPS,
            completion_criteria=STRUCTURE_COMPLETION,
            directions_tried=ctx.directions_tried,
            extra=self._findings_extra(ctx),
        )

    @staticmethod
    def _findings_extra(ctx: SubSkillContext) -> str:
        if not ctx.findings:
            return ""
        recent = ctx.findings[-10:]
        return (
            "# Prior structure/literature findings\n"
            + "\n".join(f"- {f.claim} :: {f.evidence}" for f in recent)
        )


STRUCTURE_DELIVERABLE = """Produce the paper's structural blueprint and draft sections.

## Chapter Architecture (Survey Standard)
- §1 Introduction: Hook → Gap → Contributions → Roadmap
- §2 Background: formal definitions, taxonomy overview
- §3-6 Core: one method family per chapter, with critical assessment
- §7 Benchmarks + Experiments
- §8 Future: specific open problems (Barrier + Attack vector format)
- §9 Conclusion: numbered key findings (NOT a repeat of the abstract)

## Paragraph Logic Patterns (choose the right one for each context)
| Pattern | Structure | Use Case |
|---------|-----------|----------|
| Claim-Evidence-Implication | Assert → Data → So what | Main body arguments |
| Compare-Contrast | A → B → Difference → Trade-off | Method comparison |
| Concession-Rebuttal | Admit strength → But limitation | Critical analysis |
| Funnel | Broad → Narrow → This paper | Introduction / chapter intro |

## Taxonomy Design
- Multi-axis matrix (not a flat list) — at least 2 orthogonal dimensions
- MECE: Mutually Exclusive, Collectively Exhaustive
- Empty cells in the matrix = gap analysis material (explicitly call these out)
- Spanning methods (fit in multiple cells) show taxonomy tension — this is GOOD, note it

## Formal Claims
- Default claim type: Conjecture + Remark (not Theorem — this is a survey)
- Hedge ladder (use the weakest form that still conveys the insight):
  demonstrates > suggests > indicates > may suggest > we hypothesize
- Rule: claim strength ≤ evidence strength
- EVERY core section must include at least one hedged formal claim

## Related Work Differentiation
- Mandatory comparison table with existing surveys (columns: coverage, recency, taxonomy, experiments)
- "We're more recent" is NOT sufficient differentiation
- Need structural novelty: new taxonomy dimension, new analysis angle, new experiment

## Section constraints
- Every .tex file ≤ 300 lines (EC1)
- Inter-section transitions must be present (last paragraph of §N previews §N+1)
- Terminology must be consistent across ALL sections
- Abstract and conclusion must align (same claims, same order)
"""

STRUCTURE_CAPS = (
    "Working directory: sections/*.tex. Each file ≤ 300 lines (EC1). "
    "Max 15 LLM rounds or 30 min."
)

STRUCTURE_COMPLETION = (
    "Task is complete when: (1) all 9 sections drafted as .tex files, "
    "(2) every core section (§3-6) has ≥1 formal claim with appropriate hedging, "
    "(3) comparison table with existing surveys present in §2, "
    "(4) MECE taxonomy diagram described, "
    "(5) abstract-conclusion alignment verified, "
    "(6) each file ≤ 300 lines. "
    "Emit FINDING: <claim> :: <evidence> for each structural insight. "
    "Say DONE when complete."
)
