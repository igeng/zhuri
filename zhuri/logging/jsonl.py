"""Structured JSONL logger (§6.5).

Every log line has the exact shape::

    {"ts", "source", "level", "event", "detail"}

Sources are ``work|orchestrator|heartbeat``; levels are
``info|warn|error|decision``. Decisions (e.g. pivots) are tagged
``level=decision`` so they can be filtered (§7).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from ..util import ids

SOURCES = ("work", "orchestrator", "heartbeat")
LEVELS = ("info", "warn", "error", "decision")

_LOG_FILES = {
    "work": "work.jsonl",
    "orchestrator": "orchestrator.jsonl",
    "heartbeat": "heartbeat.jsonl",
}

_LEVEL_ICONS = {
    "info": "▶",
    "warn": "⚠",
    "error": "✗",
    "decision": "✓",
}

# Module-level verbose flag; set by CLI --verbose or REPL /config verbose on.
_verbose: bool = False


def set_verbose(enabled: bool) -> None:
    """Enable or disable real-time stderr echo for all loggers."""
    global _verbose  # noqa: PLW0603
    _verbose = enabled


def is_verbose() -> bool:
    """Return current verbose state."""
    return _verbose


class JsonlLogger:
    """Append structured events to ``<task>/logs/<source>.jsonl``."""

    def __init__(self, logs_dir: str | os.PathLike, source: str, *,
                 echo: bool | None = None):
        if source not in SOURCES:
            raise ValueError(f"unknown log source: {source!r}")
        self.logs_dir = Path(logs_dir)
        self.source = source
        self.path = self.logs_dir / _LOG_FILES[source]
        self._echo = echo

    @property
    def echo(self) -> bool:
        """Whether to echo log lines to stderr (uses module flag if unset)."""
        if self._echo is not None:
            return self._echo
        return _verbose

    def log(self, event: str, *, level: str = "info", detail: str = "") -> dict:
        if level not in LEVELS:
            raise ValueError(f"unknown log level: {level!r}")
        line = {
            "ts": ids.now_iso(),
            "source": self.source,
            "level": level,
            "event": event,
            "detail": detail,
        }
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        if self.echo:
            self._echo_line(line)
        return line

    @staticmethod
    def _echo_line(line: dict) -> None:
        """Print a human-friendly log line to stderr."""
        ts = line["ts"]
        # Extract HH:MM:SS from ISO timestamp.
        time_part = ts[11:19] if len(ts) >= 19 else ts
        icon = _LEVEL_ICONS.get(line["level"], "·")
        detail = f" | {line['detail']}" if line["detail"] else ""
        print(f"[{time_part}] {icon} {line['event']}{detail}", file=sys.stderr)

    def info(self, event: str, detail: str = "") -> dict:
        return self.log(event, level="info", detail=detail)

    def warn(self, event: str, detail: str = "") -> dict:
        return self.log(event, level="warn", detail=detail)

    def error(self, event: str, detail: str = "") -> dict:
        return self.log(event, level="error", detail=detail)

    def decision(self, event: str, detail: str = "") -> dict:
        return self.log(event, level="decision", detail=detail)


def read_log(
    logs_dir: str | os.PathLike,
    source: str,
    *,
    level: str | None = None,
    tail: int | None = None,
) -> list[dict]:
    """Read back log lines, optionally filtered by level and tailed."""
    path = Path(logs_dir) / _LOG_FILES[source]
    if not path.exists():
        return []
    rows = [
        json.loads(ln)
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    if level is not None:
        rows = [r for r in rows if r.get("level") == level]
    if tail is not None:
        rows = rows[-tail:]
    return rows
