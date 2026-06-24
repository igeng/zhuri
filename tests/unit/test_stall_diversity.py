from __future__ import annotations

from zhuri.orchestrator import diversity, stall
from zhuri.state.models import Direction, Progress


def test_zero_findings_increments_stale():
    p = Progress.new("t")
    d = stall.recompute(p, new_findings=0, metric=0.0)
    assert d.stale_count == 1 and d.result == "stall"


def test_gain_resets_stale():
    p = Progress.new("t")
    p.stale_count = 3
    d = stall.recompute(p, new_findings=2, metric=5.0)
    assert d.stale_count == 0 and d.result == "gain" and d.last_metric == 5.0


def test_metric_drop_is_stall():
    p = Progress.new("t")
    p.last_metric = 10.0
    d = stall.recompute(p, new_findings=3, metric=4.0)
    assert d.result == "stall" and d.stale_count == 1


def test_pivot_at_two():
    p = Progress.new("t")
    p.stale_count = 1
    d = stall.recompute(p, new_findings=0, metric=0.0)
    assert d.action == "pivot" and d.status == "pivoting"


def test_escalate_at_four():
    p = Progress.new("t")
    p.stale_count = 3
    d = stall.recompute(p, new_findings=0, metric=0.0)
    assert d.action == "escalate" and d.status == "escalated"


def test_b2_prepared_not_executed():
    p = Progress.new("t")
    d = stall.recompute(p, new_findings=0, metric=0.0, prepared_not_executed=True)
    assert d.action == "execute" and d.stale_count == 0


def test_diversity_rejects_tried_axis():
    tried = [Direction(iteration=1, direction="x", structural_axis="framing")]
    assert not diversity.is_diverse("framing", tried)
    assert diversity.is_diverse("method", tried)


def test_propose_direction_is_diverse():
    tried = [
        Direction(iteration=1, direction="x", structural_axis="framing"),
        Direction(iteration=2, direction="y", structural_axis="data-source"),
    ]
    cand = diversity.propose_direction(tried, iteration=3, base_goal="goal")
    assert cand.structural_axis not in ("framing", "data-source")
    assert "goal" in cand.direction
