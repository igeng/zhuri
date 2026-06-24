"""Paper Structure & Logic sub-skill (§11.1 #2).

Produces a chapter architecture using a MECE taxonomy with hedged formal claims.
Each section file must stay ≤300 lines (EC1).
"""
from __future__ import annotations

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
