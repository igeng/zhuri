from __future__ import annotations

import datetime as _dt

from zhuri.state.models import Progress
from zhuri.state.store import TaskStore
from zhuri.watchdog import liveness


def _task(base, name, **ls):
    store = TaskStore(base / name)
    store.ensure_dirs()
    prog = Progress.new(name)
    for k, v in ls.items():
        setattr(prog.last_seen, k, v)
    store.write_progress(prog)
    return base / name


def test_check_no_progress_is_stale(tmp_path):
    assert liveness.check(tmp_path / "missing", "work", interval_seconds=10) == "stale"


def test_check_no_last_seen_is_stale(tmp_path):
    t = _task(tmp_path, "t")
    assert liveness.check(t, "work", interval_seconds=10) == "stale"


def test_restart_spawns(tmp_path):
    t = _task(tmp_path, "t")
    calls = []
    liveness.restart(t, spawn=lambda args, detach=False: calls.append((args, detach)))
    assert calls and calls[0][1] is True
    assert "work" in calls[0][0]


def test_nudge_spawns(tmp_path):
    t = _task(tmp_path, "t")
    calls = []
    liveness.nudge(t, spawn=lambda args, detach=False: calls.append(args))
    assert calls and "resume execution" in " ".join(calls[0])


def test_check_alive(tmp_path):
    now = _dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc)
    t = _task(tmp_path, "t", work=(now - _dt.timedelta(seconds=5)).isoformat())
    assert liveness.check(t, "work", interval_seconds=60, now=now) == "alive"
