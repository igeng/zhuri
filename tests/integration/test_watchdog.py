from __future__ import annotations

import datetime as _dt

from zhuri.state.models import Progress
from zhuri.state.store import TaskStore
from zhuri.watchdog import l0_guard, l1_patrol, liveness
from zhuri.logging.jsonl import JsonlLogger


def _task(base, name="t", **last_seen):
    store = TaskStore(base / name)
    store.ensure_dirs()
    store.write_task_spec("# Goal\nx\n")
    prog = Progress.new(name)
    for k, v in last_seen.items():
        setattr(prog.last_seen, k, v)
    store.write_progress(prog)
    return store


def test_liveness_check_alive_and_stale(tmp_path):
    now = _dt.datetime(2026, 1, 1, 12, 0, tzinfo=_dt.timezone.utc)
    fresh = (now - _dt.timedelta(minutes=1)).isoformat()
    old = (now - _dt.timedelta(hours=10)).isoformat()
    _task(tmp_path, "fresh", orchestrator=fresh)
    _task(tmp_path, "old", orchestrator=old)
    assert liveness.check(tmp_path / "fresh", "orchestrator", interval_seconds=3600, now=now) == "alive"
    assert liveness.check(tmp_path / "old", "orchestrator", interval_seconds=3600, now=now) == "stale"


def test_l1_restart_when_orchestrator_stale(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    now = _dt.datetime(2026, 1, 1, 12, 0, tzinfo=_dt.timezone.utc)
    old = (now - _dt.timedelta(hours=10)).isoformat()
    _task(base, "t", orchestrator=old, work=now.isoformat())
    spawned = []
    actions = l1_patrol.patrol(
        base, interval_seconds=3600, now=now,
        restart_fn=lambda td, **k: spawned.append(("restart", td)),
        nudge_fn=lambda td, **k: spawned.append(("nudge", td)),
    )
    assert actions[0].action == "restart"
    assert spawned and spawned[0][0] == "restart"


def test_l1_nudge_then_escalate_on_question_stall(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    now = _dt.datetime(2026, 1, 1, 12, 0, tzinfo=_dt.timezone.utc)
    old_work = (now - _dt.timedelta(hours=3)).isoformat()
    fresh_orch = (now - _dt.timedelta(minutes=1)).isoformat()
    store = _task(base, "t", orchestrator=fresh_orch, work=old_work)
    # Last work output is a question.
    JsonlLogger(store.logs_dir, "work").decision("question_stall", "should I proceed?")

    nudges = []
    actions = []
    for _ in range(3):
        # keep work stale + question each pass
        prog = store.read_progress()
        prog.last_seen.work = old_work
        prog.last_seen.orchestrator = fresh_orch
        store.write_progress(prog)
        JsonlLogger(store.logs_dir, "work").decision("question_stall", "should I proceed?")
        actions += l1_patrol.patrol(
            base, interval_seconds=3600, now=now,
            restart_fn=lambda td, **k: None,
            nudge_fn=lambda td, **k: nudges.append(td),
        )
    labels = [a.action for a in actions]
    assert labels.count("nudge") == 2
    assert labels[-1] == "escalate"
    assert store.read_progress().status == "escalated"
    assert (base / "escalations.jsonl").exists()


def test_l0_spawns_emergency_patrol_when_stale(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    now = _dt.datetime(2026, 1, 1, 12, 0, tzinfo=_dt.timezone.utc)
    old = (now - _dt.timedelta(hours=5)).isoformat()
    _task(base, "t", heartbeat=old)
    spawned = []
    res = l0_guard.check_once(
        base, now=now, spawn=lambda args, detach=False: spawned.append(args)
    )
    assert res.spawned_patrol is True
    assert spawned


def test_l0_no_spawn_when_fresh(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    now = _dt.datetime(2026, 1, 1, 12, 0, tzinfo=_dt.timezone.utc)
    fresh = (now - _dt.timedelta(minutes=5)).isoformat()
    _task(base, "t", heartbeat=fresh)
    res = l0_guard.check_once(base, now=now, spawn=lambda *a, **k: None)
    assert res.spawned_patrol is False
