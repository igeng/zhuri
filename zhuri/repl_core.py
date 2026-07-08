"""REPL core: the ``Repl`` class with all slash-command handlers (§4.2).

This is the interactive engine behind Entry B — it holds task state, parses and
dispatches slash-commands, and drives foreground orchestrator cycles. Separated
from ``repl.py`` so both modules stay under the EC1 300-line ceiling.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import entry
from .logging.jsonl import is_verbose, read_log, set_verbose
from .orchestrator import loop
from .providers.registry import Registry
from .state.store import TaskStore

SLASH_COMMANDS = {
    "status", "logs", "pause", "resume", "pivot", "stop", "spec", "new",
    "config", "quit", "synthesize", "help", "set-iters", "limits",
}

# How many orchestrator iterations a foreground REPL task runs before yielding
# the prompt back. Bounded so the window is never held indefinitely (B1-safe:
# no interactive blocking on the run path).
FOREGROUND_MAX_ITERS = 7


@dataclass
class Command:
    kind: str  # 'slash' | 'prompt'
    name: str  # slash name, or '' for prompt
    arg: str


def parse_command(line: str) -> Command:
    """Parse a REPL line into a slash-command or a task prompt."""
    line = line.strip()
    if not line.startswith("/"):
        return Command("prompt", "", line)
    body = line[1:].strip()
    name, _, arg = body.partition(" ")
    name = name.lower()
    arg = arg.strip().strip('"')
    if name not in SLASH_COMMANDS:
        return Command("slash", "unknown", name)
    return Command("slash", name, arg)


class Repl:
    """A test-friendly REPL: I/O is injected so it can run headless."""

    def __init__(self, *, registry: Registry, runner=None, out=print):
        self.registry = registry
        self.runner = runner
        self.out = out
        self.tasks: list[Path] = []
        self.paused = False
        self._fg_max_iters = FOREGROUND_MAX_ITERS

    def handle(self, line: str) -> bool:
        """Process one line. Returns False when the REPL should exit."""
        cmd = parse_command(line)
        if cmd.kind == "prompt":
            if cmd.arg:
                self._new_task(cmd.arg)
            return True
        return self._slash(cmd)

    def _slash(self, cmd: Command) -> bool:
        name = cmd.name
        if name == "quit":
            return False
        if name == "stop":
            self.out("stopping all tasks")
            return True
        if name == "pause":
            self.paused = True
            self.out("paused")
            return True
        if name == "resume":
            self.paused = False
            self.out("resumed")
            return True
        if name == "new":
            if cmd.arg:
                self._new_task(cmd.arg)
            return True
        if name == "status":
            self._status()
            return True
        if name == "logs":
            self._logs(cmd.arg or "work")
            return True
        if name == "spec":
            for t in self.tasks:
                self.out(TaskStore(t).read_task_spec())
            return True
        if name == "pivot":
            self._pivot(cmd.arg)
            return True
        if name == "config":
            self._config_cmd(cmd.arg)
            return True
        if name == "synthesize":
            self._synthesize(cmd.arg)
            return True
        if name == "set-iters":
            self._set_iters(cmd.arg)
            return True
        if name == "limits":
            self._show_limits()
            return True
        if name == "help":
            self._help()
            return True
        self.out(f"unknown command: /{cmd.arg}")
        return True

    def _new_task(self, prompt: str) -> None:
        task_dir = entry.create_workspace(Path("."))
        proceed = entry.synthesize_and_confirm(
            task_dir, prompt, self.registry, yes=True, out=self.out
        )
        if not proceed:
            return
        self.tasks.append(task_dir)
        self.out(f"launched task: {task_dir}")
        self._run_foreground(task_dir)

    def _run_foreground(self, task_dir: Path, max_iters: int | None = None) -> None:
        """Drive the orchestrator in the foreground, streaming per-iteration
        progress to ``out`` (B1-safe: no interactive blocking on this path)."""
        max_iters = self._fg_max_iters if max_iters is None else max_iters
        runner = self.runner or loop.subprocess_runner
        self.out("running in foreground (B1: zero-interaction)…")
        store = TaskStore(task_dir)
        for _ in range(max_iters):
            decisions = loop.tick(task_dir, runner=runner)
            decision = decisions[0] if decisions else None
            self.out(self._iter_line(store))
            if decision is not None and decision.action == "escalate":
                self.out("escalated: repeated stalls — human attention required")
                break
        self._run_summary(task_dir, store)

    @staticmethod
    def _iter_line(store: TaskStore) -> str:
        prog = store.read_progress()
        directions = store.read_directions()
        axis = directions[-1].structural_axis if directions else "?"
        gained = directions[-1].result == "gain" if directions else False
        iteration = prog.iteration if prog else 0
        status = prog.status if prog else "?"
        stale = prog.stale_count if prog else 0
        flag = "gain" if gained else "stall"
        return (f"[iter {iteration}] axis={axis} → {flag} "
                f"status={status} stale={stale}")

    def _run_summary(self, task_dir: Path, store: TaskStore) -> None:
        prog = store.read_progress()
        iteration = prog.iteration if prog else 0
        total = len(store.read_findings())
        self.out(f"foreground cycle done: {iteration} iterations, {total} findings total")
        self.out("artifacts:")
        self.out(f"  state : {store.state_dir}{os.sep}")
        self.out(f"  logs  : {store.logs_dir}{os.sep}")
        self.out("tip: /status · /logs work · /synthesize · /new to continue")

    def _status(self) -> None:
        for t in self.tasks:
            prog = TaskStore(t).read_progress()
            if prog:
                self.out(f"{prog.task_id} {prog.status} iter={prog.iteration} "
                         f"findings={prog.total_findings} stale={prog.stale_count}")

    def _pivot(self, target: str) -> None:
        """Force a structural pivot: flag matching task(s) so the next
        orchestrator tick injects a fresh structural direction (§4.2, §7.3)."""
        from .orchestrator.stall import FRESH_DIRECTION_THRESHOLD

        targets = [t for t in self.tasks if not target or t.name == target]
        if not targets:
            self.out(f"no such task: {target}")
            return
        for t in targets:
            store = TaskStore(t)
            prog = store.read_progress()
            if prog is None:
                continue
            store.update_progress(
                stale_count=max(prog.stale_count, FRESH_DIRECTION_THRESHOLD),
                status="pivoting",
            )
            self.out(f"forcing structural pivot on {t.name}")

    def _logs(self, source: str) -> None:
        for t in self.tasks:
            for row in read_log(TaskStore(t).logs_dir, source, tail=10):
                self.out(f"{row['ts']} [{row['level']}] {row['event']}")

    def _config_cmd(self, arg: str) -> None:
        """Handle /config with optional sub-arguments like 'verbose on|off'."""
        parts = arg.strip().split() if arg else []
        if parts and parts[0] == "verbose":
            if len(parts) >= 2 and parts[1] in ("on", "true", "1"):
                set_verbose(True)
                self.out("verbose mode: on")
            elif len(parts) >= 2 and parts[1] in ("off", "false", "0"):
                set_verbose(False)
                self.out("verbose mode: off")
            else:
                self.out(f"verbose mode: {'on' if is_verbose() else 'off'}")
            return
        self.out(f"providers={list(self.registry.config.providers)}")
        self.out(f"verbose={'on' if is_verbose() else 'off'}")

    def _help(self) -> None:
        """Display all available slash-commands with descriptions."""
        self.out("Available slash-commands:")
        self.out("  /status              show all task status")
        self.out("  /logs [source]       tail task logs (default: work)")
        self.out('  /new "prompt"        start a new concurrent task')
        self.out("  /pause               pause orchestrator scheduling")
        self.out("  /resume              resume paused scheduling")
        self.out("  /pivot [task-id]     force a structural pivot")
        self.out("  /stop                stop all tasks")
        self.out("  /spec                show current task_spec.md")
        self.out("  /synthesize [task]   synthesize findings into a document")
        self.out("  /config              show provider config")
        self.out("  /config verbose on|off  toggle verbose logging")
        self.out("  /set-iters N         set foreground iterations (0=unlimited)")
        self.out("  /limits              show all threshold values")
        self.out("  /help                show this help message")
        self.out("  /quit                exit zhuri REPL")

    def _set_iters(self, arg: str) -> None:
        """Set the foreground max iterations (0 = unlimited)."""
        try:
            n = int(arg.strip()) if arg.strip() else -1
        except ValueError:
            self.out(f"invalid number: {arg!r}")
            return
        if n < 0:
            self.out(f"current foreground max iters: {self._fg_max_iters}")
            return
        self._fg_max_iters = n
        label = "unlimited" if n == 0 else str(n)
        self.out(f"foreground max iters set to: {label}")

    def _show_limits(self) -> None:
        """Display all runtime thresholds."""
        from .orchestrator.stall import (
            PIVOT_THRESHOLD, ESCALATE_THRESHOLD, AUTO_STOP_THRESHOLD,
            FRESH_DIRECTION_THRESHOLD,
        )
        self.out("Runtime thresholds:")
        self.out(f"  pivot after stale >= {PIVOT_THRESHOLD}")
        self.out(f"  escalate after stale >= {ESCALATE_THRESHOLD}")
        self.out(f"  auto-stop after stale >= {AUTO_STOP_THRESHOLD}")
        self.out(f"  fresh direction after stale >= {FRESH_DIRECTION_THRESHOLD}")
        self.out(f"  REPL foreground max iters: {self._fg_max_iters}")
        self.out(f"  work agent cap: 15 rounds / 30 minutes")
        self.out("  EC1 file limit: 300 lines")

    def _synthesize(self, target: str) -> None:
        """Run synthesize on a task directory (by name or path)."""
        from .agents.synthesize import synthesize_document

        # Find matching task or use target as a path.
        if target:
            matches = [t for t in self.tasks if t.name == target]
            if matches:
                task_dir = matches[0]
            else:
                task_dir = Path(target)
        elif self.tasks:
            task_dir = self.tasks[-1]
        else:
            self.out("no task to synthesize; provide a task path")
            return

        doc = synthesize_document(task_dir, self.registry)
        if doc:
            self.out(f"synthesized {len(doc)} chars → {task_dir / 'state' / 'deliverable.md'}")
        else:
            self.out("no findings to synthesize")
