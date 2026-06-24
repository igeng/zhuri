from __future__ import annotations

import pytest

from zhuri.tasks.paper_writing import gates, pack
from zhuri.tasks.paper_writing.subskills import literature, review, structure


def _good_state(score=8.6, prev=8.0):
    return {
        "literature": {"references": 30, "hallucinated": 0},
        "experiment": {"has_experiments": True, "results": True},
        "structure": {"sections": 7, "max_section_lines": 200},
        "figures": {"figures": 2, "tables": 1, "error_bars": True, "has_results": True},
        "review": {
            "score": score, "phase_target": 8.5, "pdf_compiles": True,
            "prev_score": prev, "version_bumped": True, "snapshot_saved": True,
        },
    }


def test_gates_pure_and_pass():
    for name, fn in gates.ALL_GATES.items():
        passed, reasons = fn(_good_state())
        assert passed, (name, reasons)


def test_gate5_blocks_when_subgate_fails():
    state = _good_state()
    state["experiment"]["has_experiments"] = False
    passed, reasons = gates.gate_final_review(state)
    assert not passed
    assert any("experiment" in r for r in reasons)


def test_gate5_blocks_on_low_score_and_regression():
    passed, reasons = gates.gate_final_review(_good_state(score=8.0, prev=8.4))
    assert not passed
    assert any("below phase target" in r for r in reasons)
    assert any("regression" in r for r in reasons)


def test_hallucinated_citation_fails_literature_gate():
    state = _good_state()
    state["literature"]["hallucinated"] = 1
    passed, reasons = gates.gate_literature(state)
    assert not passed and any("hallucinated" in r for r in reasons)


def test_phase_routing():
    assert pack.phase_for_iteration(0) == 0
    assert pack.phase_for_iteration(3) == 1
    assert pack.phase_for_iteration(8) == 2
    assert pack.phase_for_iteration(11) == 3
    assert pack.phase_target(3) == 6.0


@pytest.mark.parametrize(
    "score,deltas,it,expected",
    [
        (8.6, [1.0], 11, True),       # score >= 8.5
        (7.0, [0.2, 0.1], 11, True),  # Δ <= 0.3 for 2 rounds
        (7.0, [1.0], 13, True),       # iter > 12
        (7.0, [1.0, 1.0], 11, False), # none
    ],
)
def test_stop_conditions(score, deltas, it, expected):
    assert pack.should_stop(score, deltas, it) is expected


def test_weakness_routing_covers_all_documented():
    for w in pack.all_weaknesses():
        r = pack.route_weakness(w)
        assert r.subskill in ("literature", "experiment", "figures", "structure")
        assert r.action
    with pytest.raises(KeyError):
        pack.route_weakness("nonexistent_weakness")


def test_weakness_routing_examples():
    assert pack.route_weakness("too many arxiv refs").subskill == "literature"
    assert pack.route_weakness("no experiments").subskill == "experiment"
    assert pack.route_weakness("no error bars").subskill == "figures"


def test_review_first_round_capped_at_7():
    out = review.review_round(
        round_index=0, reviewer_scores=[9.0, 9.0, 9.0],
        reviewer_models=["a", "b", "c"], prev_final=None,
        unresolved_weaknesses=["x"],
    )
    assert out.final_score == 7.0 and out.ok


def test_review_max_delta_1_5():
    out = review.review_round(
        round_index=1, reviewer_scores=[9.0, 9.0, 9.0],
        reviewer_models=["a", "b", "a"], prev_final=6.0,
        unresolved_weaknesses=["x"],
    )
    assert out.final_score == 7.5  # 6.0 + 1.5


def test_review_requires_unresolved_weakness():
    out = review.review_round(
        round_index=1, reviewer_scores=[7, 7, 7],
        reviewer_models=["a", "b", "c"], prev_final=6.0,
        unresolved_weaknesses=[],
    )
    assert not out.ok and any("unresolved" in v for v in out.violations)


def test_review_requires_model_diversity():
    out = review.review_round(
        round_index=1, reviewer_scores=[7, 7, 7],
        reviewer_models=["a", "a", "a"], prev_final=6.0,
        unresolved_weaknesses=["x"],
    )
    assert not out.ok and any("same model" in v for v in out.violations)


def test_review_uses_median():
    out = review.review_round(
        round_index=2, reviewer_scores=[5.0, 8.0, 8.5, 9.0, 9.0],
        reviewer_models=["a", "b", "c", "d", "e"], prev_final=8.0,
        unresolved_weaknesses=["x"],
    )
    assert out.raw_median == 8.5


def test_literature_ec4_cadence():
    assert literature.verification_points(45) == [20, 40]
    cites = [{"id": i} for i in range(45)]
    calls = []

    def verify(batch):
        calls.append(len(batch))
        return 0

    res = literature.run_survey(cites, verify=verify)
    # verification fires at 20, 40, then final partial batch of 5
    assert calls == [20, 20, 5]
    assert res.verification_rounds == [20, 40]
    assert res.collected == 45


def test_structure_mece_and_hedge():
    assert structure.is_mece(structure.plan_sections())
    assert not structure.is_mece(["a", "a"])
    assert structure.hedge_claim("X improves Y").lower().startswith("our results suggest")
