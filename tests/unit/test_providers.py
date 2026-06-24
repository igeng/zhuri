from __future__ import annotations

import asyncio

import pytest

from zhuri.config import load_config_str
from zhuri.providers.base import AuthError
from zhuri.providers.fake import FakeProvider
from zhuri.providers.registry import Registry

CFG = """
[providers.deepseek]
type = "openai_compat"
api_key = "k1"
models = ["deepseek-chat", "deepseek-reasoner"]

[agents.default]
provider = "deepseek"
model = "deepseek-chat"

[agents.review]
provider = "deepseek"
models = ["deepseek-chat", "deepseek-reasoner"]
"""


def test_complete_contract_nonstream():
    p = FakeProvider(default="hello world")
    res = asyncio.run(
        p.complete(system="s", messages=[{"role": "user", "content": "hi"}], model="m")
    )
    assert res.text == "hello world"
    assert res.model == "m"


def test_stream_contract():
    p = FakeProvider(default="a b c")

    async def collect():
        return "".join(
            [
                tok
                async for tok in p.stream(
                    system="s", messages=[{"role": "user", "content": "x"}], model="m"
                )
            ]
        )

    assert asyncio.run(collect()).strip() == "a b c"


def test_auth_failure_raises_exit3():
    p = FakeProvider(fail_auth=True)
    with pytest.raises(AuthError) as ei:
        asyncio.run(p.complete(system="s", messages=[], model="m"))
    assert ei.value.exit_code == 3


def test_pool_rotation_deterministic():
    cfg = load_config_str(CFG)
    reg = Registry(cfg, factory=lambda eff: FakeProvider())
    seq = [reg.model_for_round("review", r) for r in range(4)]
    assert seq == ["deepseek-chat", "deepseek-reasoner", "deepseek-chat", "deepseek-reasoner"]


def test_diverse_model_differs():
    cfg = load_config_str(CFG)
    reg = Registry(cfg, factory=lambda eff: FakeProvider())
    assert reg.diverse_model("review", 1, avoid="deepseek-chat") != "deepseek-chat"


def test_ends_with_question_signal():
    p = FakeProvider(default="should I proceed?")
    res = asyncio.run(p.complete(system="s", messages=[], model="m"))
    assert res.ends_with_question()
