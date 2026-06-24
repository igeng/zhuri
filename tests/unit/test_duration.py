from __future__ import annotations

import pytest

from zhuri.util.duration import DurationError, format_duration, parse_duration


@pytest.mark.parametrize(
    "text,seconds",
    [
        ("30m", 1800),
        ("2h", 7200),
        ("90s", 90),
        ("1d", 86400),
        ("1h30m", 5400),
        ("45", 45),
        ("PT2H", 7200),
        ("PT90S", 90),
        ("P1DT2H", 93600),
        ("1w", 604800),
    ],
)
def test_parse_duration_ok(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["", "  ", "abc", "2x", "1h2x", None])
def test_parse_duration_bad(text):
    with pytest.raises(DurationError):
        parse_duration(text)


def test_format_duration_roundtripish():
    assert format_duration(5400) == "1h30m"
    assert format_duration(0) == "0s"
    assert format_duration(86400) == "1d"
