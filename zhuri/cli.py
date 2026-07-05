"""Entry points for the ``zhuri`` CLI (§4).

Detects the entry mode (A / B / C) and routes to the appropriate handler.
Command dispatch and argument parsing live in :mod:`zhuri.cli_dispatch`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .cli_dispatch import SUBCOMMANDS, build_parser, dispatch
from .config import ConfigError, load_config
from .logging.jsonl import set_verbose
from .providers.base import ProviderError


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

    from .cli_dispatch import _registry_factory
    try:
        registry = _registry_factory(provider_factory)(load_config(args.config))
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return exc.exit_code

    from . import entry
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
