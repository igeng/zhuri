"""Experiment Design sub-skill (§11.1 #3).

Design → Execute (API/GPU) → Iterate (≤5) → Report. Produces results data only;
LaTeX figures are the Figures sub-skill's job.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_ITERS = 5


@dataclass
class ExperimentReport:
    iterations: int
    succeeded: bool
    results: dict = field(default_factory=dict)


def run_experiment(*, attempt, max_iters: int = MAX_ITERS) -> ExperimentReport:
    """Iterate an experiment up to ``max_iters`` times.

    ``attempt(i)`` returns ``(ok: bool, results: dict)``.
    """
    last: dict = {}
    for i in range(1, max_iters + 1):
        ok, results = attempt(i)
        last = results
        if ok:
            return ExperimentReport(iterations=i, succeeded=True, results=results)
    return ExperimentReport(iterations=max_iters, succeeded=False, results=last)
