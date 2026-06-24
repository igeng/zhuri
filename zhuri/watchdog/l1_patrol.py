"""L1 durable patrol (§8.3).

Runs hourly (via cron/systemd). For each loop: if ``now - last_seen >
interval×3`` ⇒ restart. For each task: if no update for >2h AND the last output is
a question ⇒ stalled ⇒ nudge. Three consecutive nudges with no progress ⇒ stuck ⇒
escalate. Uses only the liveness surface (check/restart/nudge) on others' tasks.
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path

from ..logging.jsonl import JsonlLogger, read_log
from ..state.store import TaskStore
from ..util import ids
from . import liveness

TWO_HOURS = 2 * 60 * 60
MAX_NUDGES = 3


@dataclass
class PatrolAction:
    task: str
    action: str  # ok|restart|nudge|escalate


def _age_seconds(value: str | None, now: _dt.datetime) -> float:
    if not value:
        return float("inf")
    try:
        seen = _dt.datetime.fromisoformat(value)
    except ValueError:  # pragma: no cover
        return float("inf")
    return (now - seen).total_seconds()


def last_output_is_question(task_dir) -> bool:
    """Heuristic (§13.3): the last work-log line is a question stall.

    False-positive handling: a nudge only fires when this is *also* paired with a
    >2h staleness window, so an incidental '?' cannot trigger a nudge by itself.
    """
    rows = read_log(TaskStore(task_dir).logs_dir, "work", tail=1)
    if not rows:
        return False
    last = rows[-1]
    if last.get("event") == "question_stall":
        return True
    return str(last.get("detail", "")).strip().endswith("?")


def _bookkeeping_path(task_dir) -> Path:
    return TaskStore(task_dir).state_dir / "watchdog.json"


def _read_bookkeeping(task_dir) -> dict:
    p = _bookkeeping_path(task_dir)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"nudges": 0, "last_total_findings": -1}


def _write_bookkeeping(task_dir, data: dict) -> None:
    p = _bookkeeping_path(task_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _escalate(base_dir: Path, task_dir, detail: str) -> None:
    store = TaskStore(task_dir)
    store.update_progress(status="escalated")
    record = {
        "ts": ids.now_iso(),
        "task_id": Path(task_dir).name,
        "detail": detail,
        "report": "Three consecutive nudges with no progress; task is stuck (EC6).",
        "reply_hook": "file:" + str(base_dir / "reply.flag"),
    }
    with open(base_dir / "escalations.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def patrol_task(
    base_dir: Path,
    task_dir: Path,
    *,
    interval_seconds: float,
    now: _dt.datetime,
    logger: JsonlLogger,
    restart_fn=liveness.restart,
    nudge_fn=liveness.nudge,
) -> PatrolAction:
    name = Path(task_dir).name
    store = TaskStore(task_dir)
    progress = store.read_progress()
    if progress is None:
        return PatrolAction(name, "ok")

    # Loop liveness: restart orchestrator if past interval×3.
    orch_age = _age_seconds(progress.last_seen.orchestrator, now)
    if orch_age > interval_seconds * 3:
        restart_fn(task_dir)
        logger.warn("restart", detail=f"task={name} orchestrator stale {orch_age:.0f}s")
        return PatrolAction(name, "restart")

    # Task stall: no update >2h AND trailing question ⇒ nudge.
    work_age = _age_seconds(progress.last_seen.work, now)
    if work_age > TWO_HOURS and last_output_is_question(task_dir):
        book = _read_bookkeeping(task_dir)
        made_progress = progress.total_findings > book.get("last_total_findings", -1)
        if made_progress:
            book["nudges"] = 0
        book["nudges"] = book.get("nudges", 0) + 1
        book["last_total_findings"] = progress.total_findings
        _write_bookkeeping(task_dir, book)
        if book["nudges"] >= MAX_NUDGES and not made_progress:
            logger.decision("escalate", detail=f"task={name} stuck after {book['nudges']} nudges")
            _escalate(base_dir, task_dir, f"{book['nudges']} nudges, no progress")
            return PatrolAction(name, "escalate")
        nudge_fn(task_dir)
        logger.warn("nudge", detail=f"task={name} nudge #{book['nudges']}")
        return PatrolAction(name, "nudge")

    return PatrolAction(name, "ok")


def patrol(
    base_dir: str | Path,
    *,
    interval_seconds: float,
    now: _dt.datetime | None = None,
    restart_fn=liveness.restart,
    nudge_fn=liveness.nudge,
) -> list[PatrolAction]:
    """Run one L1 patrol pass over all tasks under ``base_dir``."""
    from ..orchestrator.loop import discover_tasks

    base = Path(base_dir)
    now = now or ids.now()
    actions = []
    for task_dir in discover_tasks(base):
        store = TaskStore(task_dir)
        store.ensure_dirs()
        # L2/B3: heartbeat callback updates its own last_seen first.
        store.touch_last_seen("heartbeat")
        logger = JsonlLogger(store.logs_dir, "heartbeat")
        actions.append(
            patrol_task(
                base,
                task_dir,
                interval_seconds=interval_seconds,
                now=now,
                logger=logger,
                restart_fn=restart_fn,
                nudge_fn=nudge_fn,
            )
        )
    return actions
