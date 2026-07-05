"""Academic Figures & Tables sub-skill (§11.1 #4).

Builds booktabs tables and vector figures from ``results.json``. Figures derived
from result data MUST include error bars (±std).

:class:`FiguresTablesSkill` encodes booktabs rules, quality checklist, tool
priority hierarchy, and quantity targets as a prompt template.
"""
from __future__ import annotations

from zhuri.agents.prompt import WorkPrompt, build_prompt
from zhuri.tasks.base import SubSkill, SubSkillContext


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


# ---------------------------------------------------------------------------
# FiguresTablesSkill — prompt-builder for the work agent
# ---------------------------------------------------------------------------

class FiguresTablesSkill(SubSkill):
    name = "figures"
    description = (
        "Booktabs tables + vector figures from results.json with quality checklist"
    )

    def build_prompt(self, ctx: SubSkillContext) -> WorkPrompt:
        return build_prompt(
            background=ctx.task_spec[:3000] or "Create academic figures and tables.",
            deliverable=FIGURES_DELIVERABLE,
            working_dir=ctx.extra or ".",
            caps=FIGURES_CAPS,
            completion_criteria=FIGURES_COMPLETION,
            directions_tried=ctx.directions_tried,
            extra=self._findings_extra(ctx),
        )

    @staticmethod
    def _findings_extra(ctx: SubSkillContext) -> str:
        if not ctx.findings:
            return ""
        recent = ctx.findings[-10:]
        return (
            "# Prior results/experiment findings\n"
            + "\n".join(f"- {f.claim} :: {f.evidence}" for f in recent)
        )


FIGURES_DELIVERABLE = r"""Create presentation-quality academic figures and tables from results.json.

## Table Types (pick the right one for each dataset)
| Type | Use Case | Information Density |
|------|----------|-------------------|
| Comparison Matrix | Methods × features summary | Very high |
| Benchmark Table | Models × metrics | High |
| Ablation Table | Conditions × results | High |
| Taxonomy Table | Classification visualization | Medium |
| Meta-analysis | Aggregated cross-paper data | Very high |

## Table Design Rules (ALL tables must follow)
1. **Booktabs style ONLY**: `\toprule`, `\midrule`, `\bottomrule` — NO vertical lines
2. **Alternating row color**: `\rowcolor{gray!6}` on every other row
3. **Bold best results** in each column with `\textbf{}`
4. **All experimental data**: mean ± std (never mean alone)
5. **Caption must contain the key finding**, not just a description
   - WRONG: "Results of experiments on GLUE benchmark."
   - RIGHT: "BERT-large outperforms all baselines on GLUE (84.1%), with the largest margin on RTE (+3.2%). Error bars = ±1 std over 5 runs."
6. **Every table/ figure must be referenced** in the main text

## Figure Tool Priority (highest to lowest)
1. **TikZ** — programmatic LaTeX diagrams (architecture, flow charts)
2. **matplotlib → PDF** — data-driven plots (curves, bars, heatmaps)
3. **SVG → PDF** — diagrams from external tools
4. **PIL → PNG** — simple schematics (acceptable per reviewer feedback, ≥300 DPI)

## Quality Checklist (verify before output)
- [ ] Vector format (PDF) preferred; PNG ≥ 300 DPI if raster
- [ ] Font size ≥ 10pt after scaling to column width
- [ ] Academic palette: blue #2196F3, red #F44336, green #4CAF50, orange #FF9800
- [ ] All axes labeled with units
- [ ] All plot lines have a legend
- [ ] Light grid (alpha=0.3) for readability in data plots
- [ ] Each figure/table is self-contained (understandable without reading main text)

## Quantity Targets
- Full survey (50+ pages): ≥ 10 tables, ≥ 6 figures
- Short survey (30 pages): ≥ 5 tables, ≥ 3 figures
"""

FIGURES_CAPS = (
    "Working directory: figures/*.pdf + tables/*.tex. "
    "Max 15 LLM rounds or 30 min."
)

FIGURES_COMPLETION = (
    "Task is complete when: (1) all tables use booktabs format (no vertical lines), "
    "(2) every experimental-data table includes mean ± std, "
    "(3) every figure/table caption contains a conclusion, "
    "(4) quantity targets met for the paper's length, "
    "(5) all items pass the quality checklist. "
    "Emit FINDING: <claim> :: <evidence> for each visualization insight. "
    "Say DONE when complete."
)
