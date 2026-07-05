"""Quality gates for the paper-writing pack (§11.4).

Five gates; each is a **pure function** ``gate(state) -> (passed, reasons)``.
Gates 1&2 may run in parallel; Gate 5 is **blocking** (requires 1–4 passed, a
clean PDF compile, score ≥ phase target, no regression, version bump + snapshot).

All thresholds are sourced from the upstream Scientific Paper Writing Skill Group
v2.0 (June 2026).
"""
from __future__ import annotations

GateResult = tuple[bool, list[str]]


# ---------------------------------------------------------------------------
# Gate 1 — Literature
# ---------------------------------------------------------------------------

def gate_literature(state: dict) -> GateResult:
    lit = state.get("literature", {})
    reasons: list[str] = []
    total = lit.get("citations", 0)
    if total < 80:
        reasons.append(f"citations={total} < 80 minimum (draft)")
    year_dist = lit.get("within_1yr_pct", 0)
    if year_dist < 40:
        reasons.append(f"within-1yr={year_dist}% < 40% threshold")
    accepted_pct = lit.get("accepted_pct", 0)
    if accepted_pct < 30:
        reasons.append(f"accepted={accepted_pct}% < 30% threshold")
    arxiv_pct = lit.get("arxiv_only_pct", 100)
    if arxiv_pct > 60:
        reasons.append(f"arXiv-only={arxiv_pct}% > 60% limit")
    verify_rate = lit.get("verification_rate", 0)
    if verify_rate < 80:
        reasons.append(f"verification_rate={verify_rate}% < 80% threshold")
    hallucinated = lit.get("hallucinated", 0)
    if hallucinated > 0:
        reasons.append(f"{hallucinated} hallucinated citations (must be 0, EC4)")
    cells_missing = lit.get("taxonomy_cells_missing_refs", 0)
    if cells_missing > 0:
        reasons.append(f"{cells_missing} taxonomy cells lack ≥2 A/B references")
    return (not reasons, reasons)


# ---------------------------------------------------------------------------
# Gate 2 — Experiment
# ---------------------------------------------------------------------------

def gate_experiment(state: dict) -> GateResult:
    exp = state.get("experiment", {})
    reasons: list[str] = []
    if not exp.get("hypothesis_preregistered"):
        reasons.append("no hypothesis pre-registered before execution")
    if not exp.get("statistical_test_reported"):
        reasons.append("no statistical test reported (p-value or confidence interval)")
    if exp.get("trials", 0) < 3:
        reasons.append(f"trials={exp.get('trials', 0)} < 3 minimum")
    if not exp.get("has_std"):
        reasons.append("no standard deviation reported (mean±std required)")
    if exp.get("ceiling_effect"):
        reasons.append("ceiling effect detected — increase difficulty or redesign")
    if exp.get("floor_effect"):
        reasons.append("floor effect detected — check for bugs or simplify")
    if not exp.get("links_to_claim"):
        reasons.append("experiment does not link to a specific paper claim")
    if not exp.get("has_results"):
        reasons.append("no results.json produced")
    return (not reasons, reasons)


# ---------------------------------------------------------------------------
# Gate 3 — Structure
# ---------------------------------------------------------------------------

def gate_structure(state: dict) -> GateResult:
    st = state.get("structure", {})
    reasons: list[str] = []
    if st.get("sections", 0) < 1:
        reasons.append("no sections written")
    if st.get("max_section_lines", 0) > 300:
        reasons.append(f"max section lines={st['max_section_lines']} exceeds 300 (EC1)")
    if st.get("compile_errors", -1) != 0:
        reasons.append(f"compile errors={st.get('compile_errors')} (must be 0)")
    if st.get("undefined_refs", -1) != 0:
        reasons.append(f"undefined references={st.get('undefined_refs')} (must be 0)")
    if not st.get("abstract_conclusion_aligned"):
        reasons.append("abstract and conclusion not aligned")
    if not st.get("inter_section_transitions"):
        reasons.append("inter-section transitions missing")
    if not st.get("critical_assessment"):
        reasons.append("no critical assessment in core sections")
    if st.get("formal_claims", 0) < 1:
        reasons.append("no formal claims (conjecture/observation) in core sections")
    if not st.get("terminology_consistent"):
        reasons.append("terminology inconsistent across sections")
    return (not reasons, reasons)


# ---------------------------------------------------------------------------
# Gate 4 — Figures & Tables
# ---------------------------------------------------------------------------

def gate_figures(state: dict) -> GateResult:
    fig = state.get("figures", {})
    reasons: list[str] = []
    tables = fig.get("tables", 0)
    figures = fig.get("figures", 0)
    if tables < 5 and figures < 3:
        reasons.append(f"tables={tables} < 5 and figures={figures} < 3 (short survey minimum)")
    if not fig.get("booktabs_format"):
        reasons.append("tables not in booktabs format (no vertical lines)")
    if fig.get("has_results") and not fig.get("error_bars", False):
        reasons.append("experimental figures lack error bars (±std)")
    if not fig.get("captions_contain_conclusion"):
        reasons.append("captions describe but do not conclude")
    if not fig.get("all_referenced"):
        reasons.append("not all figures/tables are referenced in text")
    if not fig.get("nontrivial_insight"):
        reasons.append("at least one figure/table should carry a non-trivial insight")
    return (not reasons, reasons)


# ---------------------------------------------------------------------------
# Gate 5 — Final Review (BLOCKING)
# ---------------------------------------------------------------------------

def gate_final_review(state: dict) -> GateResult:
    """Gate 5 — blocking. Requires gates 1–4 to pass plus review conditions."""
    reasons: list[str] = []
    for name, fn in (
        ("literature", gate_literature),
        ("experiment", gate_experiment),
        ("structure", gate_structure),
        ("figures", gate_figures),
    ):
        passed, why = fn(state)
        if not passed:
            reasons.append(f"gate {name} failed: {'; '.join(why)}")

    rev = state.get("review", {})
    score = rev.get("score")
    target = rev.get("phase_target", 8.5)
    if not rev.get("pdf_compiles", False):
        reasons.append("PDF does not compile cleanly")
    if score is None:
        reasons.append("no review score available")
    elif score < target:
        reasons.append(f"score {score} below phase target {target}")

    prev = rev.get("prev_score")
    if prev is not None and score is not None and score < prev:
        reasons.append(f"regression: score {score} < previous {prev}")

    if not rev.get("version_bumped", False):
        reasons.append("version not bumped")
    if not rev.get("snapshot_saved", False):
        reasons.append("snapshot not saved")

    # Regression of previously-fixed weaknesses
    regressed = rev.get("regressed_weaknesses", [])
    if regressed:
        reasons.append(f"regressed weaknesses: {', '.join(regressed)}")

    return (not reasons, reasons)


# ---------------------------------------------------------------------------
# Gate registry
# ---------------------------------------------------------------------------

ALL_GATES = {
    "literature": gate_literature,
    "experiment": gate_experiment,
    "structure": gate_structure,
    "figures": gate_figures,
    "final_review": gate_final_review,
}
