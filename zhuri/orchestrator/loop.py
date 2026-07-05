"""Orchestrator loop: monitor → detect → inject → launch (§7.1).

The orchestrator may run as the current session or a durable cron. Each tick:
1. updates orchestrator ``last_seen`` first (B3);
2. for each task: reads progress, injects a fresh structural direction when
   stalling, launches a work agent (subprocess by default), reads back state and
   recomputes stall (§7.2);
3. logs decisions at ``level=decision``; escalations are surfaced (§8.5).
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..logging.jsonl import JsonlLogger
from ..state.models import Direction
from ..state.store import TaskStore
from ..util import ids, proc
from . import diversity, stall

# A work runner takes (task_dir, direction) and returns (new_findings, metric).
WorkRunner = Callable[[Path, str], "RunOutcome"]


@dataclass
class RunOutcome:
    new_findings: int
    metric: float | None
    prepared_not_executed: bool = False


def discover_tasks(base_dir: str | Path) -> list[Path]:
    """Return task directories under ``base_dir`` (or base_dir itself)."""
    base = Path(base_dir)
    if (base / "state").exists():
        return [base]
    tasks = []
    for child in sorted(base.iterdir()) if base.exists() else []:
        if child.is_dir() and (child / "state").exists():
            tasks.append(child)
    return tasks


def subprocess_runner(task_dir: Path, direction: str) -> RunOutcome:
    """Default runner: spawn ``zhuri work`` as a real subprocess (B4 isolation)."""
    before = len(TaskStore(task_dir).read_findings())
    result = proc.run(
        [sys.executable, "-m", "zhuri", "work", str(task_dir), "--direction", direction],
        timeout=60 * 35,
    )
    store = TaskStore(task_dir)
    after = len(store.read_findings())
    new = after - before
    return RunOutcome(new_findings=new, metric=float(new))


def _base_goal(store: TaskStore) -> str:
    spec = store.read_task_spec()
    for line in spec.splitlines():
        if line.strip() and not line.startswith("#"):
            return line.strip()[:160]
    return store.task_dir.name


def _escalate(base_dir: Path, store: TaskStore, detail: str) -> None:
    record = {
        "ts": ids.now_iso(),
        "task_id": store.task_dir.name,
        "detail": detail,
        "report": "Full escalation: repeated stalls; human attention required (EC6).",
        "reply_hook": "file:" + str(base_dir / "reply.flag"),
    }
    path = base_dir / "escalations.jsonl"
    # Atomic append via temp + rename (mirrors TaskStore convention).
    tmp = path.with_name(f".{path.name}.{ids.pid()}.{ids.new_id()}.tmp")
    # Read existing lines, append, write atomically.
    existing = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(existing)
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _route_review_weaknesses(store: TaskStore, logger: JsonlLogger) -> list[str]:
    """Read review outcome from state/ and return weakness-route suggestions.

    Looks for ``review_outcome.json`` in the task state directory.  If found,
    extracts each weakness's ``route_to`` field and logs it as a decision so the
    orchestrator can inject it as the next direction.  This is the feedback
    loop described in §SPEC-TODO §二.
    """
    import json as _json

    review_path = store.state_dir / "review_outcome.json"
    if not review_path.exists():
        return []

    try:
        review = _json.loads(review_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    suggestions: list[str] = []
    for reviewer in review.get("reviewers", []):
        for w in reviewer.get("weaknesses", []):
            route = w.get("route_to", "").strip().lower()
            severity = w.get("severity", "Minor")
            if route and severity == "Major":
                suggestions.append(f"subskill:{route}")
                logger.decision(
                    "weakness_routed",
                    detail=f"severity={severity} route={route} "
                    f"weakness={w.get('text', '')[:120]}"
                )
    return suggestions


def tick_task(
    base_dir: Path,
    task_dir: Path,
    *,
    runner: WorkRunner,
    logger: JsonlLogger,
) -> stall.StallDecision:
    """Run one orchestrator iteration for a single task."""
    store = TaskStore(task_dir)
    progress = store.read_progress()
    if progress is None:
        from ..state.models import Progress

        progress = Progress.new(task_dir.name)
        store.write_progress(progress)

    tried = store.read_directions()
    iteration = progress.iteration + 1

    # ---------- feedback loop: review weakness → sub-skill direction ----------
    weakness_directions = _route_review_weaknesses(store, logger)
    direction_override = weakness_directions[0] if weakness_directions else None
    # --------------------------------------------------------------------------

    candidate = diversity.propose_direction(
        tried,
        iteration=iteration,
        base_goal=_base_goal(store),
        override=direction_override,
    )
    if stall.needs_fresh_direction(progress):
        logger.decision("fresh_direction", detail=f"axis={candidate.structural_axis}")

    outcome = runner(task_dir, candidate.direction)

    decision = stall.recompute(
        store.read_progress(),
        new_findings=outcome.new_findings,
        metric=outcome.metric,
        prepared_not_executed=outcome.prepared_not_executed,
    )

    candidate.result = decision.result
    store.append_direction(candidate)
    # Advance iteration idempotently: the work agent already bumps it on the real
    # path; with a mock runner this records the completed cycle (max avoids
    # double-counting).
    current_iter = store.read_progress().iteration
    store.update_progress(
        iteration=max(current_iter, iteration),
        stale_count=decision.stale_count,
        status=decision.status,
        last_metric=decision.last_metric,
    )

    if decision.action == "pivot":
        logger.decision(
            "pivot",
            detail=f"stale={decision.stale_count} axis={candidate.structural_axis}",
        )
    elif decision.action == "escalate":
        logger.decision("escalate", detail=f"stale={decision.stale_count}")
        _escalate(base_dir, store, f"stale_count={decision.stale_count}")
    elif decision.action == "execute":
        logger.decision("execute_now", detail="prepared-but-not-executed (B2)")
    return decision


def tick(
    base_dir: str | Path,
    *,
    runner: WorkRunner | None = None,
) -> list[stall.StallDecision]:
    """Run one orchestrator tick over all tasks (single ``--once`` cycle)."""
    base = Path(base_dir)
    runner = runner or subprocess_runner
    decisions = []
    tasks = discover_tasks(base)
    for task_dir in tasks:
        store = TaskStore(task_dir)
        store.ensure_dirs()
        # B3: orchestrator reports alive first.
        store.touch_last_seen("orchestrator")
        logger = JsonlLogger(store.logs_dir, "orchestrator")
        progress = store.read_progress()
        iteration = (progress.iteration + 1) if progress else 1
        print(f"  [orch] tick  task={task_dir.name}  iteration={iteration}",
              flush=True)
        decisions.append(tick_task(base, task_dir, runner=runner, logger=logger))
    return decisions
