"""L0 resident guard (§8.2).

A tiny, session-independent guard that watches only the heartbeat timestamp. If
the most recent heartbeat is stale (> 2h by default) it spins up an emergency
patrol via a headless process. L0 MUST NOT read task findings (B5).

True session independence is achieved by installing this as a ``systemd`` unit or
a shell ``while`` loop (recipes documented in the README and validated by
``zhuri doctor``).
"""
from __future__ import annotations

import datetime as _dt
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from ..state.store import TaskStore
from ..util import ids, proc

STALE_THRESHOLD = 2 * 60 * 60  # > 2h (§8.1 L0)


@dataclass
class GuardResult:
    heartbeat_age: float
    spawned_patrol: bool


def _latest_heartbeat(base_dir: Path, now: _dt.datetime) -> float:
    """Age (seconds) of the freshest heartbeat ``last_seen`` across tasks.

    Reads only ``last_seen`` timestamps — never findings (B5).
    """
    from ..orchestrator.loop import discover_tasks

    youngest = float("inf")
    for task_dir in discover_tasks(base_dir):
        progress = TaskStore(task_dir).read_progress()
        if progress is None or not progress.last_seen.heartbeat:
            continue
        try:
            seen = _dt.datetime.fromisoformat(progress.last_seen.heartbeat)
        except ValueError:  # pragma: no cover
            continue
        youngest = min(youngest, (now - seen).total_seconds())
    return youngest


def _spawn_emergency_patrol(base_dir: Path, interval: str, spawn) -> object:
    args = [sys.executable, "-m", "zhuri", "watchdog", str(base_dir), "--interval", interval]
    return spawn(args, detach=True)


def check_once(
    base_dir: str | Path,
    *,
    threshold_seconds: float = STALE_THRESHOLD,
    interval: str = "1h",
    now: _dt.datetime | None = None,
    spawn=None,
) -> GuardResult:
    """One L0 check: spawn an emergency patrol when the heartbeat is stale."""
    base = Path(base_dir)
    now = now or ids.now()
    spawn = spawn or proc.spawn
    age = _latest_heartbeat(base, now)
    if age > threshold_seconds:
        _spawn_emergency_patrol(base, interval, spawn)
        return GuardResult(heartbeat_age=age, spawned_patrol=True)
    return GuardResult(heartbeat_age=age, spawned_patrol=False)


def run_guard(
    base_dir: str | Path,
    *,
    poll_seconds: float = 300.0,
    threshold_seconds: float = STALE_THRESHOLD,
    interval: str = "1h",
    iterations: int | None = None,
) -> None:  # pragma: no cover - long-running loop
    """Resident loop. ``iterations`` bounds it for tests/manual runs."""
    count = 0
    while iterations is None or count < iterations:
        check_once(base_dir, threshold_seconds=threshold_seconds, interval=interval)
        count += 1
        if iterations is not None and count >= iterations:
            break
        time.sleep(poll_seconds)
