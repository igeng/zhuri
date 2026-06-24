"""Welcome banner for the zhuri REPL (§4.4 Rich TTY output).

Renders a Claude Code / OpenCode-style welcome panel when the user enters the
interactive REPL (Entry B). Includes version, working directory, tips, and
available slash-commands.
"""
from __future__ import annotations

import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__


def render_banner(working_dir: Path | None = None, console: Console | None = None) -> None:
    """Print the zhuri welcome banner to the terminal."""
    console = console or Console()
    working_dir = working_dir or Path.cwd()

    # Build a two-column table: left (branding), right (tips)
    grid = Table.grid(padding=(0, 3))
    grid.add_column(justify="center", min_width=28)
    grid.add_column()

    # Left column content
    left = Text()
    left.append("\n")
    left.append("Welcome to zhuri!\n", style="bold")
    left.append("\n")
    left.append("    ☀️  逐日  ☀️\n", style="yellow")
    left.append("  chasing the sun\n", style="dim italic")
    left.append("\n")
    left.append(f"v{__version__}", style="cyan")
    left.append(" · ")
    left.append(str(working_dir), style="green")
    left.append("\n")

    # Right column content
    right = Text()
    right.append("Tips for getting started\n", style="bold")
    right.append("Type a task in natural language and press Enter\n")
    right.append("Use /help to see all slash-commands\n")
    right.append("─" * 50 + "\n", style="dim")
    right.append("Slash-commands\n", style="bold")
    right.append("/status", style="cyan")
    right.append("      show task status\n")
    right.append("/logs", style="cyan")
    right.append("        tail task logs\n")
    right.append("/new", style="cyan")
    right.append("         start a new concurrent task\n")
    right.append("/pause", style="cyan")
    right.append("       pause current tasks\n")
    right.append("/resume", style="cyan")
    right.append("      resume paused tasks\n")
    right.append("/pivot", style="cyan")
    right.append("       force a structural pivot\n")
    right.append("/stop", style="cyan")
    right.append("        stop all tasks\n")
    right.append("/spec", style="cyan")
    right.append("        show task_spec.md\n")
    right.append("/synthesize", style="cyan")
    right.append("  synthesize findings into document\n")
    right.append("/config", style="cyan")
    right.append("      show provider config\n")
    right.append("/help", style="cyan")
    right.append("        show all slash-commands\n")
    right.append("/quit", style="cyan")
    right.append("        exit zhuri\n")

    grid.add_row(left, right)

    panel = Panel(
        grid,
        title=f"[bold]zhuri v{__version__}[/bold]",
        border_style="bright_blue",
        expand=True,
    )
    console.print(panel)


def render_prompt(console: Console | None = None) -> None:
    """Print the prompt separator line."""
    console = console or Console()
    width = console.width or 80
    console.print("─" * width, style="dim")
    console.print("❯ ", style="bold green", end="")
