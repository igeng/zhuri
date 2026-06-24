"""Literature Survey sub-skill (§11.1 #1) with EC4 verification cadence.

EC4: citation-like content MUST be verified **every 20 entries**, never batched
to the end. :func:`verification_points` returns the indices at which verification
fires; :func:`run_survey` interleaves verification into collection.
"""
from __future__ import annotations

from dataclasses import dataclass, field

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
