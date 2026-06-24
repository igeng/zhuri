from __future__ import annotations

import asyncio

from zhuri.agents import subagent
from zhuri.agents.subagent import pattern_a, pattern_b, pattern_c_async, pattern_d, reconcile
from zhuri.config import load_config_str
from zhuri.providers.base import ProviderResult
from zhuri.providers.fake import FakeProvider
from zhuri.providers.registry import Registry
from zhuri.state.models import Finding
from zhuri.state.store import TaskStore

CFG = """
[providers.deepseek]
type = "openai_compat"
api_key = "k"
models = ["deepseek-chat"]

[agents.default]
provider = "deepseek"
model = "deepseek-chat"

[agents.work]
provider = "deepseek"
model = "deepseek-chat"

[agents.subagent.verification]
provider = "deepseek"
model = "deepseek-chat"
"""


def _reg(provider):
    return Registry(load_config_str(CFG), factory=lambda eff: provider)


def test_pattern_a_writes_verifiable_findings(tmp_path):
    reg = _reg(FakeProvider(default="FINDING: claim1 :: strong evidence"))
    rep = pattern_a(tmp_path / "t", reg, goal="study X")
    assert rep.findings and rep.findings[0].verifiable
    assert TaskStore(tmp_path / "t").read_findings()[0].claim == "claim1"


def test_pattern_b_runs_concurrently(tmp_path):
    TaskStore(tmp_path / "t").ensure_dirs()

    class SlowProvider(FakeProvider):
        active = 0
        max_active = 0

        async def complete(self, **kw):
            type(self).active += 1
            type(self).max_active = max(type(self).max_active, type(self).active)
            await asyncio.sleep(0.05)
            type(self).active -= 1
            return ProviderResult(text="FINDING: a :: b", model=kw["model"])

    reg = _reg(SlowProvider())
    reports = pattern_b(tmp_path / "t", reg, subproblems=["p1", "p2", "p3"])
    assert len(reports) == 3
    # Concurrency: more than one subagent ran at the same time (not serial).
    assert SlowProvider.max_active >= 2


def test_pattern_b_reconcile_dedups(tmp_path):
    reports = [
        subagent.SubagentReport("p1", "", "m", [Finding("dup", "e", 0)]),
        subagent.SubagentReport("p2", "", "m", [Finding("dup", "e", 0), Finding("u", "e", 0)]),
    ]
    merged = reconcile(reports)
    assert {f.claim for f in merged} == {"dup", "u"}


def test_pattern_c_polls_after_submit_and_retries():
    events = []

    async def submit():
        events.append("submit")
        return {"id": len([e for e in events if e == "submit"])}

    statuses = iter(["error", "running", "done"])

    async def poll(handle):
        events.append("poll")
        return next(statuses)

    async def fix(handle):
        events.append("fix")

    res = asyncio.run(pattern_c_async(submit=submit, poll=poll, fix=fix))
    assert res.succeeded is True
    assert res.submits == 2  # initial + one retry after error
    assert events[0] == "submit" and events[1] == "poll"  # polling right after submit


def test_pattern_d_independent_flags_unsupported(tmp_path):
    TaskStore(tmp_path / "t").ensure_dirs()
    reg = _reg(FakeProvider(default="FLAG: bad claim"))
    out = pattern_d(tmp_path / "t", reg, [Finding("bad claim", "", 0)])
    assert "bad claim" in out["flagged"]


def test_subrole_routing_inherits_parent(tmp_path):
    # subagent.research unset → inherits from work
    captured = {}

    class CapProvider(FakeProvider):
        async def complete(self, **kw):
            captured["model"] = kw["model"]
            return ProviderResult(text="FINDING: a :: b", model=kw["model"])

    reg = _reg(CapProvider())
    pattern_a(tmp_path / "t", reg, goal="g")
    assert captured["model"] == "deepseek-chat"
