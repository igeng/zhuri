"""Stall detection + pivot/escalation decisions (§7.2, §7.3)."""
from __future__ import annotations

from dataclasses import dataclass

from ..state.models import Progress

PIVOT_THRESHOLD = 2
ESCALATE_THRESHOLD = 4
FRESH_DIRECTION_THRESHOLD = 3


@dataclass
class StallDecision:
    """Outcome of recomputing stall after an iteration."""

    stale_count: int
    result: str  # stall|gain
    status: str
    action: str  # continue|pivot|escalate|execute
    last_metric: float | None


def recompute(
    progress: Progress,
    *,
    new_findings: int,
    metric: float | None,
    prepared_not_executed: bool = False,
) -> StallDecision:
    """Apply the §7.2/§7.3 stall table to ``progress`` (does not persist).

    - 0 new findings OR a metric drop ⇒ ``stale_count += 1``.
    - otherwise reset ``stale_count`` and update ``last_metric``.
    - B2 guard: prepared-but-not-executed yields an ``execute`` action instead of
      counting a stall.
    """
    prev_metric = progress.last_metric
    if prepared_not_executed:
        return StallDecision(
            stale_count=progress.stale_count,
            result="stall",
            status="running",
            action="execute",
            last_metric=prev_metric,
        )

    metric_dropped = (
        metric is not None
        and prev_metric is not None
        and metric < prev_metric
    )
    # A metric drop alone is not a stall if we still have new findings —
    # diminishing returns are natural as easy findings are exhausted.
    # Only flag a stall when findings are zero OR the metric drops sharply
    # (>50%) while findings are very low (≤1).
    significant_drop = (
        metric_dropped
        and prev_metric is not None
        and metric is not None
        and prev_metric > 0
        and (metric / prev_metric) < 0.5
        and new_findings <= 1
    )
    is_stall = new_findings == 0 or significant_drop

    if is_stall:
        stale = progress.stale_count + 1
        result = "stall"
        new_last_metric = prev_metric
    else:
        stale = 0
        result = "gain"
        new_last_metric = metric if metric is not None else prev_metric

    status = "running"
    action = "continue"
    if stale >= ESCALATE_THRESHOLD:
        status = "escalated"
        action = "escalate"
    elif stale >= PIVOT_THRESHOLD:
        status = "pivoting"
        action = "pivot"

    return StallDecision(
        stale_count=stale,
        result=result,
        status=status,
        action=action,
        last_metric=new_last_metric,
    )


def needs_fresh_direction(progress: Progress) -> bool:
    """§7.1.2: regenerate a fresh direction before launch when stalling."""
    return progress.stale_count >= FRESH_DIRECTION_THRESHOLD
