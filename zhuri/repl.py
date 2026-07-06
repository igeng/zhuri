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


def _read_multiline(prompt: str = "❯ ") -> str:
    """Read a possibly multi-line input from the user.

    After the first line, probes stdin for buffered lines (e.g. from a paste).
    Accumulates all immediately-available lines into one prompt, joined by
    newlines.  Stops when no more buffered data is available.
    """
    first = input(prompt)
    if not first.strip():
        return first

    # Check for buffered (pasted) lines.
    extra_lines: list[str] = []
    try:
        # Windows: use msvcrt to probe the console buffer.
        import msvcrt as _msvcrt
        while _msvcrt.kbhit():
            raw = _msvcrt.getwche()
            line = ""
            while raw != "\n" and raw != "\r":
                line += raw
                if not _msvcrt.kbhit():
                    break
                raw = _msvcrt.getwche()
            extra_lines.append(line)
            # After \r, check for \n (CRLF).
            if raw == "\r" and _msvcrt.kbhit():
                nxt = _msvcrt.getwche()
                if nxt != "\n":
                    line += nxt
    except (ImportError, OSError):
        # Unix fallback: use select with a short timeout.
        try:
            import select as _select
            while _select.select([sys.stdin], [], [], 0.05)[0]:
                line = sys.stdin.readline()
                if not line:
                    break
                extra_lines.append(line.rstrip("\n\r"))
        except (ImportError, OSError):
            pass

    if extra_lines:
        return first + "\n" + "\n".join(extra_lines)
    return first


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
