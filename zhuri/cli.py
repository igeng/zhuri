"""Argument parsing + command dispatch (thin) — §4.5 command table.

Entry detection: no args ⇒ REPL (Entry B); a bare prompt string ⇒ Entry A;
otherwise dispatch the named subcommand. Exit codes: 0 ok, 1 generic, 2 config,
3 provider/auth (§4.4).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config_cmd, entry
from .config import ConfigError, load_config
from .logging.jsonl import read_log, set_verbose
from .providers.base import ProviderError
from .providers.registry import Registry
from .state.store import TaskStore
from .util.duration import parse_duration

SUBCOMMANDS = {
    "init", "run", "watchdog", "guard", "work", "status", "logs", "config",
    "doctor", "repl", "synthesize",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="zhuri", add_help=True)
    p.add_argument("--config", default=None, help="path to config.toml")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="enable real-time log output to stderr")
    sub = p.add_subparsers(dest="command")
    a = sub.add_parser("init")
    a.add_argument("task_dir")
    a.add_argument("--template", default="blank", choices=["blank", "paper-writing"])
    r = sub.add_parser("run")
    r.add_argument("base_dir")
    r.add_argument("--interval", default="2h")
    r.add_argument("--max-iters", type=int, default=None)
    r.add_argument("--once", action="store_true")
    w = sub.add_parser("watchdog")
    w.add_argument("base_dir")
    w.add_argument("--interval", default="1h")
    g = sub.add_parser("guard")
    g.add_argument("base_dir")
    g.add_argument("--iterations", type=int, default=1)
    wk = sub.add_parser("work")
    wk.add_argument("task_dir")
    wk.add_argument("--direction", required=True)
    wk.add_argument("--max-rounds", type=int, default=15)
    wk.add_argument("--max-minutes", type=float, default=30.0)
    s = sub.add_parser("status")
    s.add_argument("base_dir")
    s.add_argument("--watch", action="store_true")
    s.add_argument("--json", action="store_true")
    lg = sub.add_parser("logs")
    lg.add_argument("task_dir")
    lg.add_argument("--source", default="work", choices=["work", "orchestrator", "heartbeat"])
    lg.add_argument("--level", default=None)
    lg.add_argument("--follow", action="store_true")
    lg.add_argument("--tail", type=int, default=50)
    c = sub.add_parser("config")
    c.add_argument("action", nargs="?", default="path",
                   choices=["get", "set", "path", "check"])
    c.add_argument("--role", default=None)
    c.add_argument("--effective", action="store_true")
    c.add_argument("--json", action="store_true")
    d = sub.add_parser("doctor")
    d.add_argument("--offline", action="store_true")
    sub.add_parser("repl")
    syn = sub.add_parser("synthesize")
    syn.add_argument("task_dir")
    return p


def _make_config_fn(args):
    return lambda: load_config(getattr(args, "config", None))


def _registry_factory(provider_factory):
    if provider_factory is None:
        return lambda cfg: Registry(cfg)
    return lambda cfg: Registry(cfg, factory=provider_factory)


def dispatch(args, *, provider_factory=None, runner=None) -> int:
    make_config = _make_config_fn(args)
    reg_factory = _registry_factory(provider_factory)
    cmd = args.command
    if getattr(args, "verbose", False):
        set_verbose(True)

    if cmd == "init":
        entry.scaffold_task(Path(args.task_dir), args.template)
        print(f"scaffolded {args.task_dir} ({args.template})")
        return 0

    if cmd == "run":
        once = args.once
        interval = parse_duration(args.interval)
        entry.run_orchestrator(
            Path(args.base_dir), runner=runner, max_iters=args.max_iters,
            interval_seconds=interval, once=once,
        )
        return 0

    if cmd == "watchdog":
        from .watchdog import l1_patrol
        l1_patrol.patrol(Path(args.base_dir), interval_seconds=parse_duration(args.interval))
        return 0

    if cmd == "guard":
        from .watchdog import l0_guard
        l0_guard.run_guard(Path(args.base_dir), iterations=args.iterations, poll_seconds=0)
        return 0

    if cmd == "work":
        from .agents.work_agent import run_work
        registry = reg_factory(make_config())
        run_work(Path(args.task_dir), args.direction, registry,
                 max_rounds=args.max_rounds, max_minutes=args.max_minutes)
        return 0

    if cmd == "synthesize":
        from .agents.synthesize import synthesize_document
        registry = reg_factory(make_config())
        doc = synthesize_document(Path(args.task_dir), registry)
        if doc:
            print(doc)
        else:
            print("no findings to synthesize", file=sys.stderr)
            return 1
        return 0

    if cmd == "status":
        return _status(args)

    if cmd == "logs":
        rows = read_log(TaskStore(args.task_dir).logs_dir, args.source,
                        level=args.level, tail=args.tail)
        for row in rows:
            print(f"{row['ts']} [{row['level']}] {row['event']} {row['detail']}")
        return 0

    if cmd == "config":
        return config_cmd.config_command(args, make_config=make_config)

    if cmd == "doctor":
        return config_cmd.doctor_command(args, make_config=make_config,
                                         registry_factory=reg_factory)

    if cmd == "repl":
        from .repl import run_repl
        return run_repl(provider_factory=provider_factory, runner=runner)

    return 2


def _status(args, *, sleep=None, cycles=None, interval_seconds=2.0) -> int:
    import time as _time
    sleep = sleep or _time.sleep
    if not getattr(args, "watch", False):
        _render_status(args)
        return 0
    count = 0
    while cycles is None or count < cycles:
        _render_status(args)
        count += 1
        if cycles is not None and count >= cycles:
            break
        sleep(interval_seconds)
    return 0


def _render_status(args) -> None:
    import json as _json
    from .orchestrator.loop import discover_tasks
    out = []
    for task_dir in discover_tasks(Path(args.base_dir)):
        prog = TaskStore(task_dir).read_progress()
        if prog is None:
            continue
        out.append({
            "task_id": prog.task_id, "iteration": prog.iteration,
            "status": prog.status, "total_findings": prog.total_findings,
            "stale_count": prog.stale_count,
        })
    if args.json:
        print(_json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for row in out:
            print(f"{row['task_id']:<24} {row['status']:<10} "
                  f"iter={row['iteration']} findings={row['total_findings']} "
                  f"stale={row['stale_count']}")


def main(argv=None, *, provider_factory=None, runner=None, spawn=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        from .repl import run_repl
        return run_repl(provider_factory=provider_factory, runner=runner)

    # Check if only --dir (and optionally --config/--verbose) are provided → REPL with dir.
    repl_parser = argparse.ArgumentParser(add_help=False)
    repl_parser.add_argument("--dir", default=None)
    repl_parser.add_argument("--config", default=None)
    repl_parser.add_argument("-v", "--verbose", action="store_true")
    repl_args, remaining = repl_parser.parse_known_args(argv)
    if not remaining and (repl_args.dir or repl_args.verbose):
        if repl_args.verbose:
            set_verbose(True)
        from .repl import run_repl
        wd = Path(repl_args.dir) if repl_args.dir else None
        return run_repl(provider_factory=provider_factory, runner=runner,
                        working_dir=wd)

    # Entry A: a bare prompt (first token not a subcommand and not a flag).
    if argv[0] not in SUBCOMMANDS and not argv[0].startswith("-"):
        return _entry_a(argv, provider_factory=provider_factory, runner=runner,
                        spawn=spawn)

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        return dispatch(args, provider_factory=provider_factory, runner=runner)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return exc.exit_code
    except ProviderError as exc:
        print(f"provider error: {exc}", file=sys.stderr)
        return getattr(exc, "exit_code", 1)


def _entry_a(argv, *, provider_factory=None, runner=None, spawn=None) -> int:
    p = argparse.ArgumentParser(prog="zhuri")
    p.add_argument("prompt")
    p.add_argument("--config", default=None)
    p.add_argument("--dir", default=".")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--detach", action="store_true")
    p.add_argument("--direct", action="store_true",
                   help="skip iterations; produce result in one LLM call")
    p.add_argument("--synthesize", action="store_true",
                   help="produce a final document after iterations complete")
    p.add_argument("--max-iters", type=int, default=None)
    p.add_argument("--once", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="enable real-time log output to stderr")
    args = p.parse_args(argv)
    if args.verbose:
        set_verbose(True)
    try:
        registry = _registry_factory(provider_factory)(load_config(args.config))
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return exc.exit_code
    task_dir = entry.create_workspace(Path(args.dir))
    proceed = entry.synthesize_and_confirm(task_dir, args.prompt, registry, yes=args.yes)
    if not proceed:
        print("aborted before run start")
        return 0
    if args.direct:
        return _direct_mode(task_dir, args.prompt, registry)
    base = task_dir
    if args.detach:
        from .util import proc
        spawn = spawn or proc.spawn
        cmd = [sys.executable, "-m", "zhuri"]
        if args.config:
            cmd += ["--config", args.config]
        cmd += ["run", str(base)]
        if args.max_iters is not None:
            cmd += ["--max-iters", str(args.max_iters)]
        if args.once:
            cmd += ["--once"]
        spawn(cmd, detach=True)
        print(f"launched (detached): {task_dir}")
        return 0
    entry.run_orchestrator(base, runner=runner, max_iters=args.max_iters,
                           once=args.once)
    if args.synthesize:
        from .agents.synthesize import synthesize_document
        doc = synthesize_document(task_dir, registry)
        if doc:
            print("\n--- Final Document ---\n")
            print(doc)
    print(f"task completed at {task_dir}")
    return 0


def _direct_mode(task_dir: Path, prompt: str, registry) -> int:
    """Direct mode: single LLM call producing the final deliverable immediately."""
    from .agents.synthesize import direct_generate
    doc = direct_generate(task_dir, prompt, registry)
    if doc:
        print(doc)
    return 0
