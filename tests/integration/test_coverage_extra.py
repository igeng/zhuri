from __future__ import annotations

import os
from pathlib import Path

import pytest

from zhuri.config import Config, ConfigError, config_path, load_config_str
from zhuri.orchestrator import loop


def test_base_url_interpolation_missing_nonstrict(monkeypatch):
    monkeypatch.delenv("MISSING_HOST", raising=False)
    text = """
[providers.x]
type = "openai_compat"
base_url = "${MISSING_HOST}/v1"
api_key = "k"
models = ["m"]

[agents.default]
provider = "x"
model = "m"
"""
    cfg = load_config_str(text)
    # Non-strict interpolation drops the missing var → "/v1".
    assert cfg.provider_base_url("x") == "/v1"


def test_cyclic_default_without_provider():
    text = """
[providers.x]
api_key = "k"
models = ["m"]

[agents.default]
model = "m"
"""
    cfg = load_config_str(text)
    with pytest.raises(ConfigError):
        cfg.resolve_role("default")


def test_check_iterates_nested_subroles():
    text = """
[providers.x]
type = "openai_compat"
base_url = "http://x/v1"
api_key = "k"
models = ["m"]

[agents.default]
provider = "x"
model = "m"

[agents.subagent.verification]
provider = "x"
model = "m"
"""
    cfg = load_config_str(text)
    assert cfg.check() == []


def test_check_nested_subrole_bad_model():
    text = """
[providers.x]
type = "openai_compat"
base_url = "http://x/v1"
api_key = "k"
models = ["m"]

[agents.default]
provider = "x"
model = "m"

[agents.subagent.verification]
provider = "x"
model = "not-listed"
"""
    cfg = load_config_str(text)
    assert any("not listed" in e for e in cfg.check())


def test_config_path_project_override(tmp_path, monkeypatch):
    monkeypatch.delenv("ZHURI_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    proj = tmp_path / ".zhuri" / "config.toml"
    proj.parent.mkdir(parents=True)
    proj.write_text("[providers.x]\napi_key='k'\n")
    assert config_path() == proj


def test_config_path_home_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("ZHURI_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)  # no ./.zhuri/config.toml here
    p = config_path()
    assert p.name == "config.toml" and ".config/zhuri" in str(p)


def test_subprocess_runner_with_fake_provider(tmp_path, monkeypatch):
    from zhuri.state.models import Progress
    from zhuri.state.store import TaskStore

    cfg = tmp_path / "c.toml"
    cfg.write_text(
        "[providers.x]\ntype='openai_compat'\nbase_url='http://x/v1'\napi_key='k'\n"
        "models=['m']\n[agents.default]\nprovider='x'\nmodel='m'\n"
        "[agents.work]\nprovider='x'\nmodel='m'\n"
    )
    task = tmp_path / "t"
    store = TaskStore(task)
    store.ensure_dirs()
    store.write_task_spec("# Goal\nx\n")
    store.write_progress(Progress.new("t"))

    monkeypatch.setenv("ZHURI_CONFIG", str(cfg))
    monkeypatch.setenv("ZHURI_FAKE_PROVIDER", "1")
    monkeypatch.setenv("ZHURI_FAKE_TEXT", "FINDING: viaproc :: e\nDONE")
    outcome = loop.subprocess_runner(task, "explore")
    assert outcome.new_findings == 1
