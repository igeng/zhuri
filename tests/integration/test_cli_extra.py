from __future__ import annotations

from pathlib import Path

from zhuri import cli
from zhuri.config import load_config_str
from zhuri.logging.jsonl import JsonlLogger
from zhuri.orchestrator import diversity, loop
from zhuri.orchestrator.loop import RunOutcome
from zhuri.providers.fake import FakeProvider
from zhuri.providers.registry import Registry
from zhuri.repl import Repl
from zhuri.state.models import Direction, Progress
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
"""


def _cfg_file(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(CFG)
    return p


def test_logs_command(tmp_path, capsys):
    cfg = _cfg_file(tmp_path)
    t = tmp_path / "t"
    TaskStore(t).ensure_dirs()
    JsonlLogger(TaskStore(t).logs_dir, "work").info("hello", "world")
    rc = cli.main(["--config", str(cfg), "logs", str(t), "--source", "work"])
    out = capsys.readouterr().out
    assert rc == 0 and "hello" in out


def test_status_text(tmp_path, capsys):
    cfg = _cfg_file(tmp_path)
    base = tmp_path / "base"
    cli.main(["--config", str(cfg), "init", str(base / "task-a")])
    rc = cli.main(["--config", str(cfg), "status", str(base)])
    assert rc == 0 and "task-a" in capsys.readouterr().out


def test_status_watch_cycles(tmp_path, capsys):
    from types import SimpleNamespace

    cfg = _cfg_file(tmp_path)
    base = tmp_path / "base"
    cli.main(["--config", str(cfg), "init", str(base / "task-a")])
    capsys.readouterr()  # discard scaffold output
    args = SimpleNamespace(base_dir=str(base), json=False, watch=True)
    sleeps = []
    rc = cli._status(args, sleep=sleeps.append, cycles=3)
    out = capsys.readouterr().out
    assert rc == 0
    assert out.count("task-a") == 3  # rendered once per cycle
    assert len(sleeps) == 2  # sleeps only between cycles


def test_entry_a_detach_spawns_background(tmp_path):
    cfg = _cfg_file(tmp_path)
    calls = []

    def fake_spawn(cmd, *, detach=False):
        calls.append((cmd, detach))
        return None

    spec = "# Goal\nG\n\n## Milestones\n1. a\n\n## Success criteria\n- x\n"
    rc = cli.main(
        ["study agents", "--config", str(cfg), "--dir", str(tmp_path),
         "--yes", "--detach"],
        provider_factory=lambda eff: FakeProvider(default=spec),
        spawn=fake_spawn,
    )
    assert rc == 0
    assert len(calls) == 1
    cmd, detach = calls[0]
    assert detach is True
    assert "run" in cmd


def test_config_path_and_get(tmp_path, capsys):
    cfg = _cfg_file(tmp_path)
    assert cli.main(["--config", str(cfg), "config", "path"]) == 0
    assert cli.main(["--config", str(cfg), "config", "get", "--json"]) == 0
    assert cli.main(["--config", str(cfg), "config", "set"]) == 0


def test_no_subcommand_prints_help(capsys):
    assert cli.main(["--config", "x"]) == 0


def test_watchdog_and_guard_commands(tmp_path):
    cfg = _cfg_file(tmp_path)
    base = tmp_path / "base"
    cli.main(["--config", str(cfg), "init", str(base / "task-a")])
    assert cli.main(["--config", str(cfg), "watchdog", str(base), "--interval", "1h"]) == 0
    assert cli.main(["--config", str(cfg), "guard", str(base), "--iterations", "1"]) == 0


def test_work_command(tmp_path):
    cfg = _cfg_file(tmp_path)
    t = tmp_path / "t"
    store = TaskStore(t)
    store.ensure_dirs()
    store.write_task_spec("# Goal\nx\n")
    store.write_progress(Progress.new("t"))
    rc = cli.main(
        ["--config", str(cfg), "work", str(t), "--direction", "d", "--max-rounds", "1"],
        provider_factory=lambda eff: FakeProvider(default="FINDING: a :: b\nDONE"),
    )
    assert rc == 0 and len(store.read_findings()) == 1


def test_doctor_live_probe_passes(tmp_path, capsys):
    cfg = _cfg_file(tmp_path)
    rc = cli.main(
        ["--config", str(cfg), "doctor"],
        provider_factory=lambda eff: FakeProvider(default="pong"),
    )
    assert rc == 0 and "auth probes passed" in capsys.readouterr().out


def test_doctor_live_probe_auth_fail(tmp_path):
    cfg = _cfg_file(tmp_path)
    rc = cli.main(
        ["--config", str(cfg), "doctor"],
        provider_factory=lambda eff: FakeProvider(fail_auth=True),
    )
    assert rc == 3


def test_repl_control_commands(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    reg = Registry(load_config_str(CFG), factory=lambda eff: FakeProvider(
        default="# Goal\nG\n\n## Milestones\n1. a\n\n## Success criteria\n- x\n"))
    out = []
    r = Repl(registry=reg, out=out.append)
    assert r.handle("/pause") and r.paused
    assert r.handle("/resume") and not r.paused
    assert r.handle("/stop")
    assert r.handle("/config")
    assert r.handle('/new "another task"')
    assert r.handle("/logs work")
    assert r.handle("/pivot task-a")
    assert r.handle("/bogus")
    assert r.handle("") is True  # empty prompt ignored
    assert r.handle("/quit") is False


def test_repl_pivot_forces_structural_pivot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = "# Goal\nG\n\n## Milestones\n1. a\n\n## Success criteria\n- x\n"
    reg = Registry(load_config_str(CFG), factory=lambda eff: FakeProvider(default=spec))
    out = []
    r = Repl(registry=reg, out=out.append)
    r.handle('/new "do research"')
    assert r.tasks
    task = r.tasks[0]
    r.handle(f"/pivot {task.name}")
    prog = TaskStore(task).read_progress()
    assert prog.status == "pivoting"
    assert prog.stale_count >= 3
    # Unknown task name is reported, not silently applied.
    out.clear()
    r.handle("/pivot no-such-task")
    assert any("no such task" in m for m in out)


def test_diversity_axis_exhaustion():
    tried = [Direction(iteration=i, direction="d", structural_axis=a)
             for i, a in enumerate(diversity.STRUCTURAL_AXES)]
    # All axes used → wraps deterministically.
    axis = diversity.next_axis(tried)
    assert axis in diversity.STRUCTURAL_AXES


def test_loop_base_goal_fallback(tmp_path):
    base = tmp_path / "base"
    t = base / "task-a"
    store = TaskStore(t)
    store.ensure_dirs()
    store.write_task_spec("# only a heading\n")
    store.write_progress(Progress.new("task-a"))
    loop.tick(base, runner=lambda td, d: RunOutcome(new_findings=1, metric=1.0))
    assert store.read_directions()


def test_discover_single_task_dir(tmp_path):
    t = tmp_path / "solo"
    TaskStore(t).ensure_dirs()
    assert loop.discover_tasks(t) == [t]
