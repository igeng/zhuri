"""Task workspace creation, spec confirmation, and run launch (§4.2).

Shared by Entry A (one-shot), Entry B (REPL), and Entry C (config/scaffold). All
three converge on ``state/task_spec.md`` + the orchestrator.
"""
from __future__ import annotations

import time
from pathlib import Path

from .agents.spec_synthesis import synthesize_spec
from .orchestrator import loop
from .orchestrator.loop import WorkRunner
from .providers.registry import Registry
from .state.models import Progress
from .state.store import TaskStore
from .util import ids

TEMPLATES = {
    "blank": "# Goal\n<describe the goal>\n\n## Milestones\n1. \n\n## Success criteria\n- \n",
    "paper-writing": (
        "# Goal\nWrite a publishable scientific paper on <topic>.\n\n"
        "## Milestones\n1. Literature survey\n2. Structure & logic\n"
        "3. Experiments\n4. Figures & tables\n5. Peer-review loop to score >= 8.5\n\n"
        "## Success criteria\n- Median reviewer score >= 8.5\n- PDF compiles clean\n\n"
        "## Initial direction seed\nStart with Phase 0 topic selection.\n"
    ),
}


def create_workspace(base_dir: Path, task_id: str | None = None) -> Path:
    """Create ``<base>/.zhuri/tasks/<id>`` (or a given task dir) with state/logs."""
    task_id = task_id or ids.new_id("task")
    task_dir = Path(base_dir) / ".zhuri" / "tasks" / task_id
    store = TaskStore(task_dir)
    store.ensure_dirs()
    return task_dir


def scaffold_task(task_dir: Path, template: str = "blank") -> Path:
    """Entry C: scaffold a task directory with a template task_spec.md."""
    if template not in TEMPLATES:
        raise ValueError(f"unknown template: {template!r}")
    store = TaskStore(task_dir)
    store.ensure_dirs()
    store.write_task_spec(TEMPLATES[template])
    store.write_progress(Progress.new(Path(task_dir).name))
    return Path(task_dir)


def synthesize_and_confirm(
    task_dir: Path,
    prompt: str,
    registry: Registry,
    *,
    yes: bool = False,
    confirm=None,
    out=print,
) -> bool:
    """Spec synthesis → single pre-run confirmation (exempt from B1, §4.3).

    Returns True if the run should proceed. ``--yes`` (``yes=True``) skips the
    confirmation entirely. Once a run starts, B1 is absolute.
    """
    spec = synthesize_spec(task_dir, prompt, registry)
    if yes:
        return True
    out("\n--- synthesized task_spec.md ---\n" + spec + "\n--------------------------------")
    if confirm is None:
        confirm = lambda: input("Start the run? [y/N] ").strip().lower() in ("y", "yes")
    return bool(confirm())


def run_orchestrator(
    base_dir: Path,
    *,
    runner: WorkRunner | None = None,
    max_iters: int | None = None,
    interval_seconds: float = 2 * 60 * 60,
    once: bool = False,
    sleep=time.sleep,
) -> int:
    """Drive the orchestrator loop (B1: zero interaction on the run path).

    Stops when: (a) ``--once`` or ``max_iters`` reached, or (b) all discovered
    tasks are in a terminal state (done / auto-stopped escalated).
    """
    from .orchestrator.stall import is_terminal

    iters = 0
    while True:
        loop.tick(base_dir, runner=runner)
        iters += 1
        if once or (max_iters is not None and iters >= max_iters):
            break

        # Check if all tasks are terminal — if so, nothing left to do.
        tasks = loop.discover_tasks(base_dir)
        if tasks and all(
            is_terminal(TaskStore(t).read_progress() or Progress.new(""))
            for t in tasks
        ):
            print("  [zhuri] all tasks terminal — orchestrator stopping", flush=True)
            break

        sleep(interval_seconds)
    return iters
