"""Academic Figures & Tables sub-skill (§11.1 #4).

Builds booktabs tables and vector figures from ``results.json``. Figures derived
from result data MUST include error bars (±std).
"""
from __future__ import annotations


def booktabs_table(headers: list[str], rows: list[list]) -> str:
    """Render a minimal booktabs LaTeX table."""
    col = "l" * len(headers)
    lines = [
        "\\begin{tabular}{" + col + "}",
        "\\toprule",
        " & ".join(headers) + " \\\\",
        "\\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(str(c) for c in row) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines)


def figure_has_error_bars(series: dict) -> bool:
    """A result series is plottable only if it carries a ``std`` field."""
    return "std" in series and series["std"] is not None
