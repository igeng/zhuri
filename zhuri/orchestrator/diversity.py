"""Direction-diversity enforcement (§7.4).

A new direction MUST differ from every tried direction, compared on a
``structural_axis`` key (not raw string). After a stall, a perturbation strategy
is injected (opposite hypothesis / structurally-different framing). With multiple
candidates, prefer diversity over depth (EC5).
"""
from __future__ import annotations

from ..state.models import Direction

# A catalog of structural axes a pivot can move along (§7.3: change structure,
# not tactics). Ordered so successive pivots traverse distinct axes.
STRUCTURAL_AXES = (
    "framing",
    "data-source",
    "method",
    "scope",
    "evaluation",
    "abstraction-level",
    "adversarial-refutation",
    "cross-domain-analogy",
)


def tried_axes(tried: list[Direction]) -> set[str]:
    return {d.structural_axis for d in tried if d.structural_axis}


def is_diverse(candidate_axis: str, tried: list[Direction]) -> bool:
    """True if ``candidate_axis`` differs from every tried structural axis."""
    return candidate_axis not in tried_axes(tried)


def next_axis(tried: list[Direction]) -> str:
    """Return the first structural axis not yet tried (wraps if exhausted)."""
    used = tried_axes(tried)
    for axis in STRUCTURAL_AXES:
        if axis not in used:
            return axis
    # Exhausted: rotate based on count to keep moving.
    return STRUCTURAL_AXES[len(tried) % len(STRUCTURAL_AXES)]


def perturbation(axis: str, base_goal: str) -> str:
    """Build a perturbed direction description for a given structural axis."""
    templates = {
        "framing": f"Reframe the problem from the opposite hypothesis: {base_goal}",
        "data-source": f"Switch the primary evidence source for: {base_goal}",
        "method": f"Apply a structurally different method to: {base_goal}",
        "scope": f"Narrow/widen the scope boundary of: {base_goal}",
        "evaluation": f"Change the success metric/evaluation for: {base_goal}",
        "abstraction-level": f"Move up/down an abstraction level on: {base_goal}",
        "adversarial-refutation": f"Attempt to refute the leading claim in: {base_goal}",
        "cross-domain-analogy": f"Borrow a method from another domain for: {base_goal}",
    }
    return templates.get(axis, f"Explore a new structural axis ({axis}) for: {base_goal}")


def propose_direction(
    tried: list[Direction],
    *,
    iteration: int,
    base_goal: str,
    override: str | None = None,
) -> Direction:
    """Propose a fresh, structurally-diverse direction for the next iteration.

    If *override* is given (e.g. from a review→weakness→subskill feedback
    loop), it becomes the direction and the axis is set to ``"review_feedback"``,
    short-circuiting the normal axis rotation.
    """
    if override:
        return Direction(
            iteration=iteration,
            direction=override,
            structural_axis="review_feedback",
            result="stall",
        )
    axis = next_axis(tried)
    return Direction(
        iteration=iteration,
        direction=perturbation(axis, base_goal),
        structural_axis=axis,
        result="stall",
    )
