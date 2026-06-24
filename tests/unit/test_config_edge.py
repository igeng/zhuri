from __future__ import annotations

import pytest

from zhuri.config import Config, ConfigError, load_config, load_config_str


def test_inline_api_key_source():
    text = """
[providers.local]
type = "openai_compat"
base_url = "http://localhost:8000/v1"
api_key = "raw-inline-key"
models = ["m1"]

[agents.default]
provider = "local"
model = "m1"
"""
    cfg = load_config_str(text)
    eff = cfg.resolve_role("default")
    assert eff.key_source == "inline"
    assert eff.base_url == "http://localhost:8000/v1"


def test_no_default_role_errors():
    cfg = load_config_str("[providers.x]\napi_key='k'\nmodels=['m']\n")
    with pytest.raises(ConfigError):
        cfg.resolve_role("default")


def test_model_inherited_from_provider_models():
    text = """
[providers.x]
type = "openai_compat"
base_url = "http://x/v1"
api_key = "k"
models = ["only-model"]

[agents.default]
provider = "x"
"""
    cfg = load_config_str(text)
    assert cfg.resolve_role("default").model == "only-model"


def test_role_without_provider_inherits_default():
    text = """
[providers.x]
type = "openai_compat"
base_url = "http://x/v1"
api_key = "k"
models = ["m1", "m2"]

[agents.default]
provider = "x"
model = "m1"

[agents.review]
models = ["m2"]
"""
    cfg = load_config_str(text)
    eff = cfg.resolve_role("review")
    assert eff.provider == "x" and eff.model == "m2"


def test_unknown_preset_provider_no_base_url():
    text = """
[providers.weird]
type = "openai_compat"
api_key = "k"
models = ["m"]

[agents.default]
provider = "weird"
model = "m"
"""
    cfg = load_config_str(text)
    assert cfg.resolve_role("default").base_url == ""


def test_provider_no_api_key_errors():
    text = """
[providers.weird]
type = "openai_compat"
base_url = "http://x/v1"
models = ["m"]

[agents.default]
provider = "weird"
model = "m"
"""
    cfg = load_config_str(text)
    with pytest.raises(ConfigError) as ei:
        cfg.resolve_role("default")
    assert ei.value.exit_code == 3


def test_load_config_missing_file():
    with pytest.raises(ConfigError) as ei:
        load_config("/no/such/zhuri.toml")
    assert ei.value.exit_code == 2


def test_load_config_from_file(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("[providers.x]\napi_key='k'\nmodels=['m']\n[agents.default]\nprovider='x'\nmodel='m'\n")
    cfg = load_config(str(p))
    assert cfg.resolve_role("default").provider == "x"


def test_check_reports_inline_ok():
    text = """
[providers.x]
type = "openai_compat"
base_url = "http://x/v1"
api_key = "inline"
models = ["m"]

[agents.default]
provider = "x"
model = "m"
"""
    assert load_config_str(text).check() == []


def test_config_path_precedence(monkeypatch, tmp_path):
    from zhuri.config import config_path

    monkeypatch.setenv("ZHURI_CONFIG", str(tmp_path / "env.toml"))
    assert config_path() == tmp_path / "env.toml"
    assert config_path("/explicit.toml").name == "explicit.toml"
