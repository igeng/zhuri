from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from zhuri.state.models import Progress
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


def _make_task(base, name):
    store = TaskStore(base / name)
    store.ensure_dirs()
    store.write_task_spec("# Goal\nx\n")
    store.write_progress(Progress.new(name))
    return base / name


def _env():
    env = dict(os.environ)
    env["ZHURI_FAKE_PROVIDER"] = "1"
    env["ZHURI_FAKE_TEXT"] = "FINDING: real-subprocess :: evidence\nDONE"
    return env


def test_real_subprocess_work_agent(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(CFG)
    task = _make_task(tmp_path, "t1")
    proc = subprocess.run(
        [sys.executable, "-m", "zhuri", "--config", str(cfg), "work", str(task),
         "--direction", "explore-axis"],
        env=_env(), capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    findings = TaskStore(task).read_findings()
    assert any(f.claim == "real-subprocess" for f in findings)
    prog = TaskStore(task).read_progress()
    assert prog.last_seen.work is not None
    assert prog.iteration == 1


def test_two_work_agents_concurrent_no_corruption(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(CFG)
    t1 = _make_task(tmp_path, "t1")
    t2 = _make_task(tmp_path, "t2")
    procs = [
        subprocess.Popen(
            [sys.executable, "-m", "zhuri", "--config", str(cfg), "work", str(t),
             "--direction", "d"],
            env=_env(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        for t in (t1, t2)
    ]
    for p in procs:
        assert p.wait(timeout=120) == 0, p.stderr.read()
    # Both tasks have valid, uncorrupted progress + findings.
    for t in (t1, t2):
        prog = TaskStore(t).read_progress()
        assert prog is not None and prog.iteration == 1
        assert len(TaskStore(t).read_findings()) == 1
