"""Quality gates for the paper-writing pack (§11.4).

Five gates; each is a **pure function** ``gate(state) -> (passed, reasons)``.
Gates 1&2 may run in parallel; Gate 5 is **blocking** (requires 1–4 passed, a
clean PDF compile, score ≥ phase target, no regression, version bump + snapshot).
"""
from __future__ import annotations

GateResult = tuple[bool, list[str]]


def gate_literature(state: dict) -> GateResult:
    lit = state.get("literature", {})
    reasons: list[str] = []
    if lit.get("references", 0) < 1:
        reasons.append("no references collected")
    if lit.get("hallucinated", 0) > 0:
        reasons.append(f"{lit['hallucinated']} hallucinated citations (must be 0, EC4)")
    return (not reasons, reasons)


def gate_experiment(state: dict) -> GateResult:
    exp = state.get("experiment", {})
    reasons: list[str] = []
    if not exp.get("has_experiments"):
        reasons.append("no experiments designed")
    if not exp.get("results"):
        reasons.append("no results.json produced")
    return (not reasons, reasons)


def gate_structure(state: dict) -> GateResult:
    st = state.get("structure", {})
    reasons: list[str] = []
    if st.get("sections", 0) < 1:
        reasons.append("no sections written")
    if st.get("max_section_lines", 0) > 300:
        reasons.append("a section exceeds 300 lines (EC1)")
    return (not reasons, reasons)


def gate_figures(state: dict) -> GateResult:
    fig = state.get("figures", {})
    reasons: list[str] = []
    if fig.get("figures", 0) < 1 and fig.get("tables", 0) < 1:
        reasons.append("no figures or tables")
    if fig.get("has_results") and not fig.get("error_bars", False):
        reasons.append("figures lack error bars (±std)")
    return (not reasons, reasons)


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
        reasons.append("PDF does not compile clean")
    if score is None or score < target:
        reasons.append(f"score {score} below phase target {target}")
    prev = rev.get("prev_score")
    if prev is not None and score is not None and score < prev:
        reasons.append(f"regression: score {score} < previous {prev}")
    if not rev.get("version_bumped", False):
        reasons.append("version not bumped")
    if not rev.get("snapshot_saved", False):
        reasons.append("snapshot not saved")
    return (not reasons, reasons)


ALL_GATES = {
    "literature": gate_literature,
    "experiment": gate_experiment,
    "structure": gate_structure,
    "figures": gate_figures,
    "final_review": gate_final_review,
}
