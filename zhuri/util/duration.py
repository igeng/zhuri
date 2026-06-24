"""Duration parsing (§4.6).

Accepts compact forms like ``30m``, ``2h``, ``90s``, ``1d``, ``1h30m`` and a
subset of ISO-8601 durations (``PT2H``, ``PT90S``, ``P1DT2H``). Returns a number
of seconds (float). Centralized here so every command parses time identically.
"""
from __future__ import annotations

import re

_UNIT_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 60 * 60,
    "d": 24 * 60 * 60,
    "w": 7 * 24 * 60 * 60,
}

_COMPACT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([smhdw])", re.IGNORECASE)
_ISO_RE = re.compile(
    r"^P(?:(?P<days>\d+(?:\.\d+)?)D)?"
    r"(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$",
    re.IGNORECASE,
)


class DurationError(ValueError):
    """Raised when a duration string cannot be parsed."""


def parse_duration(text: str) -> float:
    """Parse a duration string into seconds.

    Raises :class:`DurationError` on malformed or empty input.
    """
    if text is None:
        raise DurationError("duration is required")
    raw = str(text).strip()
    if not raw:
        raise DurationError("empty duration")

    # Bare number => seconds.
    try:
        return float(raw)
    except ValueError:
        pass

    iso = _ISO_RE.match(raw)
    if iso and any(iso.groupdict().values()):
        total = 0.0
        total += float(iso.group("days") or 0) * _UNIT_SECONDS["d"]
        total += float(iso.group("hours") or 0) * _UNIT_SECONDS["h"]
        total += float(iso.group("minutes") or 0) * _UNIT_SECONDS["m"]
        total += float(iso.group("seconds") or 0) * _UNIT_SECONDS["s"]
        return total

    matches = list(_COMPACT_RE.finditer(raw))
    if not matches:
        raise DurationError(f"cannot parse duration: {text!r}")
    # Ensure the whole string is consumed by the unit tokens (no stray chars).
    consumed = "".join(m.group(0) for m in matches).replace(" ", "")
    if consumed != raw.replace(" ", ""):
        raise DurationError(f"cannot parse duration: {text!r}")
    total = 0.0
    for value, unit in (_COMPACT_RE.match(m.group(0)).groups() for m in matches):
        total += float(value) * _UNIT_SECONDS[unit.lower()]
    return total


def format_duration(seconds: float) -> str:
    """Render seconds as a compact human string (inverse-ish of parse)."""
    seconds = int(round(seconds))
    if seconds <= 0:
        return "0s"
    parts: list[str] = []
    for unit in ("d", "h", "m", "s"):
        size = _UNIT_SECONDS[unit]
        if seconds >= size:
            parts.append(f"{seconds // size}{unit}")
            seconds %= size
    return "".join(parts)
