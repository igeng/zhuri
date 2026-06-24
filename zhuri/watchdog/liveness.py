"""Liveness ops — the ONLY cross-task surface (§8.4, B5).

This module exposes **exactly three** public operations: :func:`check`,
:func:`restart`, :func:`nudge`. No function here may read a task's findings or
mutate its state beyond restart/nudge bookkeeping. A guardrail test enforces that
no other public callable is ever added (B5).
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from ..state.store import TaskStore
from ..util import ids, proc

__all__ = ["check", "restart", "nudge"]


def _parse_iso(value: str | None) -> _dt.datetime | None:
    if not value:
        return None
    try:
        return _dt.datetime.fromisoformat(value)
    except ValueError:  # pragma: no cover - defensive
        return None


def check(task_dir, role: str, *, interval_seconds: float, now=None) -> str:
    """Return ``"alive"`` or ``"stale"`` for a loop/task role's heartbeat.

    Reads only ``last_seen`` (liveness), never findings or other state (B5).
    """
    now = now or ids.now()
    progress = TaskStore(task_dir).read_progress()
    if progress is None:
        return "stale"
    seen = _parse_iso(getattr(progress.last_seen, role, None))
    if seen is None:
        return "stale"
    age = (now - seen).total_seconds()
    return "stale" if age > interval_seconds else "alive"


def restart(task_dir, *, direction: str = "watchdog-restart", spawn=None) -> object:
    """Restart a loop by spawning a fresh ``zhuri work`` process (B5: restart only).

    Does not read or mutate task findings/state; only relaunches the process.
    """
    spawn = spawn or proc.spawn
    args = [sys.executable, "-m", "zhuri", "work", str(Path(task_dir)),
            "--direction", direction]
    return spawn(args, detach=True)


def nudge(task_dir, *, spawn=None) -> object:
    """Nudge a stalled task: launch a subagent instructing it to resume execution.

    Injects only ``task_spec`` + ``progress`` context via the work entrypoint
    (B5: nudge only — no findings read, no result mutation).
    """
    spawn = spawn or proc.spawn
    args = [sys.executable, "-m", "zhuri", "work", str(Path(task_dir)),
            "--direction", "resume execution per task_spec; do not ask questions"]
    return spawn(args, detach=True)
