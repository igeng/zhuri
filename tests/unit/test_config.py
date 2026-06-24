from __future__ import annotations

import pytest

from zhuri.config import Config, ConfigError, load_config_str

BASE = """
[providers.deepseek]
type = "openai_compat"
base_url = "https://api.deepseek.com/v1"
api_key = "${DEEPSEEK_API_KEY}"
models = ["deepseek-chat", "deepseek-reasoner"]

[providers.qwen]
type = "openai_compat"
api_key = "${QWEN_API_KEY}"
models = ["qwen-max", "qwen-plus"]

[agents.default]
provider = "deepseek"
model = "deepseek-chat"

[agents.spec]
provider = "deepseek"
model = "deepseek-reasoner"

[agents.work]
provider = "qwen"
model = "qwen-max"

[agents.subagent.verification]
provider = "deepseek"
model = "deepseek-reasoner"
"""


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-123456")
    monkeypatch.setenv("QWEN_API_KEY", "sk-qwen-abcdef")


def test_resolve_default(env):
    cfg = load_config_str(BASE)
    eff = cfg.resolve_role("default")
    assert eff.provider == "deepseek"
    assert eff.model == "deepseek-chat"
    assert eff.api_key == "sk-deepseek-123456"


def test_unset_subrole_inherits_parent(env):
    cfg = load_config_str(BASE)
    # nudge is unset → inherits from work
    eff = cfg.resolve_role("subagent.nudge")
    assert eff.provider == "qwen"
    assert eff.model == "qwen-max"


def test_set_subrole_overrides(env):
    cfg = load_config_str(BASE)
    eff = cfg.resolve_role("subagent.verification")
    assert eff.provider == "deepseek"
    assert eff.model == "deepseek-reasoner"


def test_spec_role(env):
    cfg = load_config_str(BASE)
    assert cfg.resolve_role("spec").model == "deepseek-reasoner"


def test_qwen_preset_base_url(env):
    cfg = load_config_str(BASE)
    eff = cfg.resolve_role("work")
    assert "dashscope" in eff.base_url


def test_dangling_provider_ref_fails_check(env):
    text = BASE + "\n[agents.review]\nprovider = 'nope'\nmodel = 'x'\n"
    cfg = load_config_str(text)
    errors = cfg.check()
    assert any("unknown provider" in e for e in errors)


def test_unlisted_model_fails_check(env):
    text = BASE + "\n[agents.review]\nprovider = 'qwen'\nmodel = 'not-listed'\n"
    cfg = load_config_str(text)
    assert any("not listed" in e for e in cfg.check())


def test_both_model_and_models_invalid(env):
    text = BASE + "\n[agents.review]\nprovider = 'qwen'\nmodel = 'qwen-max'\nmodels = ['qwen-plus']\n"
    cfg = load_config_str(text)
    assert any("both" in e for e in cfg.check())
    with pytest.raises(ConfigError):
        cfg.resolve_role("review")


def test_missing_env_exit3(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("QWEN_API_KEY", "x")
    cfg = load_config_str(BASE)
    with pytest.raises(ConfigError) as ei:
        cfg.resolve_role("default")
    assert ei.value.exit_code == 3


def test_effective_masks_secret(env):
    cfg = load_config_str(BASE)
    masked = cfg.resolve_role("default").masked()
    assert masked["api_key"] != "sk-deepseek-123456"
    assert "*" in masked["api_key"]


def test_preset_provider_without_base_url(env, monkeypatch):
    monkeypatch.setenv("MOONSHOT_API_KEY", "sk-kimi")
    text = """
[providers.kimi]
type = "openai_compat"
models = ["kimi-k2-0905-preview"]

[agents.default]
provider = "kimi"
model = "kimi-k2-0905-preview"
"""
    cfg = load_config_str(text)
    eff = cfg.resolve_role("default")
    assert "moonshot" in eff.base_url
    assert eff.key_source == "env:MOONSHOT_API_KEY"
