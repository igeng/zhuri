"""Peer Review Simulation sub-skill (§11.1 #5, §11.5 anti-inflation).

3–5 reviewer personas score independently; the final score is the **median**.
Anti-inflation rules cap the first round at 7.0, allow at most +1.5 per round,
require ≥1 unresolved weakness to remain, and require ≥1 reviewer per round to use
a different model (ties to §10.5 per-round model diversity).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

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
