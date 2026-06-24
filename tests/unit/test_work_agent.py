from __future__ import annotations

import itertools

from zhuri.agents.spec_synthesis import pick_spec_role, synthesize_spec
from zhuri.agents.work_agent import run_work
from zhuri.config import load_config_str
from zhuri.providers.fake import FakeProvider
from zhuri.providers.registry import Registry
from zhuri.state.models import Finding
from zhuri.state.store import TaskStore

CFG = """
[providers.deepseek]
type = "openai_compat"
api_key = "k1"
models = ["deepseek-chat"]

[agents.default]
provider = "deepseek"
model = "deepseek-chat"

[agents.work]
provider = "deepseek"
model = "deepseek-chat"
"""

WELL_FORMED_SPEC = (
    "# Goal\nResearch X\n\n## Milestones\n1. a\n2. b\n\n"
    "## Success criteria\n- measurable\n\n## Out-of-scope\n- y\n\n"
    "## Initial direction seed\nstart here\n"
)


def _reg(provider):
    return Registry(load_config_str(CFG), factory=lambda eff: provider)


def test_spec_synthesis_well_formed(tmp_path):
    reg = _reg(FakeProvider(default=WELL_FORMED_SPEC))
    spec = synthesize_spec(tmp_path / "t", "study agents", reg)
    for heading in ("# Goal", "## Milestones", "## Success criteria"):
        assert heading in spec
    assert TaskStore(tmp_path / "t").read_progress() is not None


def test_spec_synthesis_fallback_when_malformed(tmp_path):
    reg = _reg(FakeProvider(default="totally unstructured response"))
    spec = synthesize_spec(tmp_path / "t", "study agents", reg)
    assert "# Goal" in spec and "## Milestones" in spec


def test_work_agent_last_seen_written_first(tmp_path):
    reg = _reg(FakeProvider(default="FINDING: a :: e\nDONE"))
    res = run_work(tmp_path / "t", "explore axis-1", reg)
    store = TaskStore(tmp_path / "t")
    prog = store.read_progress()
    assert prog.last_seen.work is not None
    assert res.new_findings == 1


def test_work_agent_round_cap(tmp_path):
    # Provider never says DONE and never emits a question → must stop at cap.
    reg = _reg(FakeProvider(default="FINDING: keep :: going"))
    res = run_work(tmp_path / "t", "axis", reg, max_rounds=3)
    assert res.rounds == 3
    assert res.stopped_reason == "max_rounds"


def test_work_agent_time_cap(tmp_path):
    reg = _reg(FakeProvider(default="FINDING: keep :: going"))
    clock = itertools.count(0, step=1000).__next__  # jumps far past deadline
    res = run_work(tmp_path / "t", "axis", reg, max_rounds=99, max_minutes=1, clock=clock)
    assert res.rounds <= 2


def test_work_agent_question_is_stall(tmp_path):
    reg = _reg(FakeProvider(default="should I proceed?"))
    res = run_work(tmp_path / "t", "axis", reg)
    assert res.stalled_on_question is True
    assert res.new_findings == 0


def test_work_agent_validation_invoked(tmp_path):
    called = {"n": 0}

    def validator(store):
        called["n"] += 1
        return True

    reg = _reg(FakeProvider(default="FINDING: a :: e\nDONE"))
    res = run_work(tmp_path / "t", "axis", reg, validator=validator)
    assert called["n"] == 1 and res.validated is True


def test_no_resume_history_injected(tmp_path):
    fake = FakeProvider(default="FINDING: a :: e\nDONE")
    reg = _reg(fake)
    run_work(tmp_path / "t", "axis", reg)
    # Only one user message per round; no assistant/history messages injected (B4).
    for call in fake.calls:
        roles = [m["role"] for m in call["messages"]]
        assert roles == ["user"]


def test_spec_role_falls_back_to_orchestrator_when_unset(tmp_path):
    # §4A: with neither [agents.spec] nor [agents.orchestrator] set, the spec
    # synthesis role MUST default to ``orchestrator`` (not ``spec``).
    reg = _reg(FakeProvider(default=WELL_FORMED_SPEC))
    assert pick_spec_role(reg) == "orchestrator"


def test_spec_role_prefers_explicit_spec():
    cfg = CFG + "\n[agents.spec]\nprovider = 'deepseek'\nmodel = 'deepseek-chat'\n"
    reg = Registry(load_config_str(cfg), factory=lambda eff: FakeProvider())
    assert pick_spec_role(reg) == "spec"


def test_work_agent_injects_prior_findings(tmp_path):
    # §6.1: a bounded slice of findings.jsonl is curated into the prompt.
    store = TaskStore(tmp_path / "t")
    store.ensure_dirs()
    store.append_finding(Finding(claim="earlier-claim", evidence="prior-evidence",
                                 iteration=1, verifiable=True))
    fake = FakeProvider(default="DONE")
    reg = _reg(fake)
    run_work(tmp_path / "t", "axis", reg, max_rounds=1)
    user_msg = fake.calls[0]["messages"][0]["content"]
    assert "earlier-claim" in user_msg and "prior-evidence" in user_msg
