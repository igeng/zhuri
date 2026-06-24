"""Paper-writing phase routing + data-driven weakness routing (§11.2, §11.3)."""
from __future__ import annotations

from dataclasses import dataclass

# §11.2 Phase routing.
PHASES = {
    0: {"name": "topic-selection", "target": 0.0, "iters": (0, 0)},
    1: {"name": "draft", "target": 6.0, "iters": (1, 6)},
    2: {"name": "deep-improvement", "target": 8.0, "iters": (7, 9)},
    3: {"name": "sprint", "target": 8.5, "iters": (10, 9999)},
}


def phase_for_iteration(iteration: int) -> int:
    if iteration <= 0:
        return 0
    if iteration <= 6:
        return 1
    if iteration <= 9:
        return 2
    return 3


def phase_target(iteration: int) -> float:
    return PHASES[phase_for_iteration(iteration)]["target"]


def should_stop(score: float, recent_deltas: list[float], iteration: int) -> bool:
    """§11.2 Phase 3 stop: score ≥ 8.5 OR Δ ≤ 0.3 for 2 rounds OR iter > 12."""
    if score >= 8.5:
        return True
    if len(recent_deltas) >= 2 and all(abs(d) <= 0.3 for d in recent_deltas[-2:]):
        return True
    if iteration > 12:
        return True
    return False


# §11.3 Weakness-routing table — data-driven (dict), not hardcoded branches.
@dataclass(frozen=True)
class Routing:
    subskill: str
    action: str


WEAKNESS_ROUTING: dict[str, Routing] = {
    "too_many_arxiv_refs": Routing("literature", "stage-4 venue upgrade"),
    "missing_recent_work": Routing("literature", "recall + classify recent venues"),
    "hallucinated_citation": Routing("literature", "verify every 20 citations (EC4)"),
    "no_experiments": Routing("experiment", "design pilot experiment"),
    "weak_baselines": Routing("experiment", "add stronger baselines"),
    "no_error_bars": Routing("figures", "add ±std error bars"),
    "ugly_tables": Routing("figures", "rebuild with booktabs"),
    "poor_structure": Routing("structure", "apply MECE chapter architecture"),
    "unhedged_claims": Routing("structure", "hedge formal claims"),
    "logic_gaps": Routing("structure", "fix paragraph logic patterns"),
}


def route_weakness(weakness: str) -> Routing:
    """Map a reviewer weakness to a responsible sub-skill + action."""
    key = weakness.strip().lower().replace(" ", "_").replace("-", "_")
    if key not in WEAKNESS_ROUTING:
        raise KeyError(f"unmapped weakness: {weakness!r}")
    return WEAKNESS_ROUTING[key]


def all_weaknesses() -> list[str]:
    return list(WEAKNESS_ROUTING.keys())
