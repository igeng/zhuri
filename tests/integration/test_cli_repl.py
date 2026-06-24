from __future__ import annotations

import json

import pytest

from zhuri import cli
from zhuri.orchestrator.loop import RunOutcome
from zhuri.providers.fake import FakeProvider
from zhuri.repl import Repl, parse_command
from zhuri.providers.registry import Registry
from zhuri.config import load_config_str
from zhuri.state.store import TaskStore

CFG_TEXT = """
[providers.deepseek]
type = "openai_compat"
api_key = "k"
models = ["deepseek-chat"]

[agents.default]
provider = "deepseek"
model = "deepseek-chat"

[agents.spec]
provider = "deepseek"
model = "deepseek-chat"

[agents.work]
provider = "deepseek"
model = "deepseek-chat"
"""

SPEC_REPLY = (
    "# Goal\nG\n\n## Milestones\n1. a\n\n## Success criteria\n- x\n"
)


@pytest.fixture
def cfg_file(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(CFG_TEXT)
    return p


def _fake_factory():
    return lambda eff: FakeProvider(default=SPEC_REPLY)


def _good_runner(task_dir, direction):
    return RunOutcome(new_findings=2, metric=2.0)


def _stall_runner(task_dir, direction):
    return RunOutcome(new_findings=0, metric=0.0)


# -- dispatch table -------------------------------------------------------
def test_init_command(tmp_path, cfg_file, capsys):
    rc = cli.main(["--config", str(cfg_file), "init", str(tmp_path / "t"),
                   "--template", "paper-writing"])
    assert rc == 0
    assert (tmp_path / "t" / "state" / "task_spec.md").exists()


def test_status_json(tmp_path, cfg_file):
    base = tmp_path / "base"
    cli.main(["--config", str(cfg_file), "init", str(base / "task-a")])
    rc = cli.main(["--config", str(cfg_file), "status", str(base), "--json"])
    assert rc == 0


def test_config_check_ok(cfg_file, monkeypatch):
    rc = cli.main(["--config", str(cfg_file), "config", "check"])
    assert rc == 0


def test_config_check_dangling(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text(CFG_TEXT + "\n[agents.review]\nprovider='nope'\nmodel='x'\n")
    rc = cli.main(["--config", str(bad), "config", "check"])
    assert rc == 2


def test_config_get_effective_masks(cfg_file, capsys):
    rc = cli.main(["--config", str(cfg_file), "config", "get", "--effective",
                   "--role", "work", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    assert '"k"' not in out  # raw key never printed


def test_config_error_exit_2_when_missing():
    rc = cli.main(["--config", "/nonexistent/zzz.toml", "config", "check"])
    assert rc == 2


def test_run_once_single_tick(tmp_path, cfg_file):
    base = tmp_path / "base"
    cli.main(["--config", str(cfg_file), "init", str(base / "task-a")])
    rc = cli.main(["--config", str(cfg_file), "run", str(base), "--once"],
                  runner=_good_runner)
    assert rc == 0
    assert TaskStore(base / "task-a").read_progress().iteration == 1


def test_doctor_offline(cfg_file):
    rc = cli.main(["--config", str(cfg_file), "doctor", "--offline"])
    assert rc == 0


# -- Entry A --------------------------------------------------------------
def test_entry_a_yes_converges_on_spec(tmp_path, cfg_file):
    rc = cli.main(
        ["my research prompt", "--config", str(cfg_file), "--dir", str(tmp_path),
         "--yes", "--max-iters", "1"],
        provider_factory=_fake_factory(), runner=_good_runner,
    )
    assert rc == 0
    specs = list((tmp_path / ".zhuri" / "tasks").glob("*/state/task_spec.md"))
    assert specs and "# Goal" in specs[0].read_text()


def test_entry_a_detach(tmp_path, cfg_file):
    rc = cli.main(
        ["prompt here", "--config", str(cfg_file), "--dir", str(tmp_path),
         "--yes", "--detach"],
        provider_factory=_fake_factory(),
    )
    assert rc == 0


# -- REPL (Entry B) -------------------------------------------------------
def test_parse_slash_commands():
    assert parse_command("/status").name == "status"
    assert parse_command('/new "do a thing"').arg == "do a thing"
    assert parse_command("/pivot task-a").arg == "task-a"
    assert parse_command("just a prompt").kind == "prompt"
    assert parse_command("/bogus").name == "unknown"


def test_repl_new_task_and_status(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    reg = Registry(load_config_str(CFG_TEXT), factory=_fake_factory())
    out_lines = []
    repl = Repl(registry=reg, runner=_good_runner, out=out_lines.append)
    assert repl.handle("study agents") is True
    assert repl.tasks
    repl.handle("/status")
    repl.handle("/spec")
    assert repl.handle("/quit") is False
    assert any("# Goal" in line for line in out_lines)


def test_repl_foreground_escalates_and_stops(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # raise the bound so the escalate threshold (4 stalls) is reachable
    monkeypatch.setattr("zhuri.repl.FOREGROUND_MAX_ITERS", 6)
    reg = Registry(load_config_str(CFG_TEXT), factory=_fake_factory())
    out_lines = []
    repl = Repl(registry=reg, runner=_stall_runner, out=out_lines.append)
    assert repl.handle("study agents") is True
    assert any("escalated" in ln for ln in out_lines)
    # bounded loop stops early on escalation rather than running all iters
    iter_lines = [ln for ln in out_lines if ln.startswith("[iter ")]
    assert len(iter_lines) < 6


def test_repl_foreground_runs_and_streams(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reg = Registry(load_config_str(CFG_TEXT), factory=_fake_factory())
    out_lines = []
    repl = Repl(registry=reg, runner=_good_runner, out=out_lines.append)
    assert repl.handle("study agents") is True

    text = "\n".join(out_lines)
    # foreground banner + one line per bounded iteration + summary
    assert "running in foreground" in text
    iter_lines = [ln for ln in out_lines if ln.startswith("[iter ")]
    assert len(iter_lines) == 3
    assert any("done:" in ln and "findings total" in ln for ln in out_lines)
    assert any("artifacts:" in ln for ln in out_lines)
    # the task was actually ticked (progress advanced on disk)
    store = TaskStore(repl.tasks[0])
    assert store.read_progress().iteration == 3
