"""Entry B — interactive REPL entry-point (§4.2, primary UX).

Opens a long-lived TTY: a prompt box accepts a task in natural language; on
submit it runs spec synthesis → confirm-once → launch, then switches to a status
dashboard. The ``Repl`` class and slash-command implementations live in
:mod:`zhuri.repl_core` so both modules stay under the EC1 300-line ceiling.

Multi-line paste handling: after reading the first line, the reader probes
stdin for buffered lines (pasted content).  If found, they are accumulated
into a single prompt so pasted paragraphs are not split across commands.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .providers.registry import Registry
from .repl_core import Repl


def _stdin_has_data(timeout: float = 0.15) -> bool:
    """Return True if stdin has buffered data ready to read (e.g. pasted text).

    Works on Unix ptys (Git Bash / MinTTY included) via ``select``, and on
    native Windows consoles via ``msvcrt.kbhit``.
    """
    try:
        import msvcrt as _msvcrt
        return _msvcrt.kbhit()
    except (ImportError, OSError):
        pass
    try:
        import select as _select
        return bool(_select.select([sys.stdin], [], [], timeout)[0])
    except (ImportError, OSError, ValueError):
        return False


def _read_multiline(prompt: str = "❯ ") -> str:
    """Read a possibly multi-line input from the user.

    Reads stdin directly instead of ``input()`` so pasted multi-line text
    (including blank lines between paragraphs) is accumulated correctly.
    Stops when no more buffered data is immediately available — the user
    can still press Enter on a blank line to submit a single-line empty
    prompt.
    """
    sys.stdout.write(prompt)
    sys.stdout.flush()

    lines: list[str] = []
    first = True

    while True:
        line = sys.stdin.readline()
        if not line:  # EOF (Ctrl+D / Ctrl+Z)
            break
        stripped = line.rstrip("\n\r")
        lines.append(stripped)
        first = False
        # If no more data in buffer, we're done reading this paste/input.
        if not _stdin_has_data():
            break

    # User typed nothing (just pressed Enter).
    if not lines:
        return ""

    return "\n".join(lines)


def run_repl(*, provider_factory=None, runner=None, input_fn=None, out=print,
             registry=None, working_dir=None,
             show_banner=True, initial_prompt: str = "") -> int:
    """Start the interactive REPL (Entry B).

    Parameters
    ----------
    working_dir : Path | None
        The directory to use as the base for task workspaces. Defaults to CWD.
    show_banner : bool
        Whether to show the welcome banner (disabled in tests).
    initial_prompt : str
        If non-empty, the REPL immediately processes this as a task prompt
        (as if the user typed it), then continues the interactive loop.
    """
    if working_dir is not None:
        os.chdir(working_dir)

    if registry is None:
        try:
            cfg = load_config(None)
        except ConfigError as exc:
            out(f"config error: {exc}")
            return exc.exit_code
        registry = Registry(cfg) if provider_factory is None else Registry(cfg, factory=provider_factory)

    # Show the Claude Code-style welcome banner (§4.4 Rich TTY output)
    if show_banner:
        try:
            from .banner import render_banner
            render_banner(working_dir=Path.cwd())
        except Exception:
            # Fallback for non-TTY environments
            out("zhuri REPL — type a task, or use slash commands; /quit to exit")
    else:
        out("zhuri REPL — type a task, or use slash commands; /quit to exit")

    repl = Repl(registry=registry, runner=runner, out=out)

    # Auto-submit initial prompt if provided (Entry A REPL integration).
    if initial_prompt.strip():
        out(f"\n❯ {initial_prompt[:120]}{'...' if len(initial_prompt) > 120 else ''}")
        repl.handle(initial_prompt.strip())

    input_fn = input_fn or (lambda: _read_multiline("❯ "))
    while True:
        try:
            line = input_fn()
        except (EOFError, KeyboardInterrupt):
            break
        if not repl.handle(line):
            break
    return 0
