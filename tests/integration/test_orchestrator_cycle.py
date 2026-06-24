from __future__ import annotations

import json

from zhuri.logging.jsonl import read_log
from zhuri.orchestrator import loop
from zhuri.orchestrator.loop import RunOutcome
from zhuri.state.models import Progress
from zhuri.state.store import TaskStore


def _make_task(base, name="task-a", goal="study agents"):
    tdir = base / name
    store = TaskStore(tdir)
    store.ensure_dirs()
    store.write_task_spec(f"# Goal\n{goal}\n")
    store.write_progress(Progress.new(name))
    return tdir


def test_full_cycle_pivot_then_escalate(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    _make_task(base)

    # Mock work runner that always stalls (0 findings).
    def stalling_runner(task_dir, direction):
        return RunOutcome(new_findings=0, metric=0.0)

    statuses = []
    for _ in range(5):
        decisions = loop.tick(base, runner=stalling_runner)
        statuses.append(decisions[0].status)

    # stale 1=running, 2=pivoting, 3=pivoting, 4=escalated
    assert "pivoting" in statuses
    assert statuses[-1] == "escalated"

    # Escalation surfaced to escalations.jsonl + progress status.
    esc = (base / "escalations.jsonl").read_text().splitlines()
    assert esc and "report" in json.loads(esc[0])
    assert TaskStore(base / "task-a").read_progress().status == "escalated"

    # Pivot logged at level=decision with an axis.
    decisions = read_log((base / "task-a") / "logs", "orchestrator", level="decision")
    assert any(d["event"] == "pivot" for d in decisions)


def test_gain_resets_and_records_direction(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    _make_task(base)

    def good_runner(task_dir, direction):
        return RunOutcome(new_findings=3, metric=3.0)

    loop.tick(base, runner=good_runner)
    store = TaskStore(base / "task-a")
    assert store.read_progress().stale_count == 0
    assert len(store.read_directions()) == 1


def test_orchestrator_writes_last_seen_first(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    _make_task(base)
    loop.tick(base, runner=lambda t, d: RunOutcome(new_findings=1, metric=1.0))
    assert TaskStore(base / "task-a").read_progress().last_seen.orchestrator is not None


def test_diverse_axes_across_iterations(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    _make_task(base)
    for _ in range(3):
        loop.tick(base, runner=lambda t, d: RunOutcome(new_findings=0, metric=0.0))
    axes = [d.structural_axis for d in TaskStore(base / "task-a").read_directions()]
    assert len(set(axes)) == len(axes)  # all distinct
