from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib

from zhuri.config import BANNED_DEPS

ROOT = Path(__file__).resolve().parent.parent.parent
PKG = ROOT / "zhuri"


def _py_files():
    return sorted(PKG.rglob("*.py"))


def test_no_source_file_over_300_lines():
    """EC1 / A11: no source file may exceed 300 lines."""
    offenders = []
    for f in _py_files():
        n = len(f.read_text(encoding="utf-8").splitlines())
        if n > 300:
            offenders.append(f"{f.relative_to(ROOT)}: {n}")
    assert not offenders, offenders


def test_no_banned_agent_framework_in_pyproject():
    """A9: no agent-framework dependency declared."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    deps = data["project"].get("dependencies", [])
    deps += data["project"].get("optional-dependencies", {}).get("dev", [])
    joined = " ".join(deps).lower()
    for banned in BANNED_DEPS:
        assert banned.lower() not in joined, banned


def test_no_blocking_input_on_run_path():
    """A12 / B1: no input() in run-path modules (only entry-confirm/REPL/config)."""
    allowed = {"repl.py", "entry.py"}  # interactive only at init/spec-confirm + REPL
    run_path = [
        PKG / "orchestrator" / "loop.py",
        PKG / "agents" / "work_agent.py",
        PKG / "agents" / "subagent.py",
        PKG / "watchdog" / "l0_guard.py",
        PKG / "watchdog" / "l1_patrol.py",
        PKG / "watchdog" / "liveness.py",
    ]
    for f in run_path:
        src = f.read_text(encoding="utf-8")
        assert "input(" not in src, f"blocking input() on run path: {f.name}"


def test_no_resume_history_in_work_path():
    """B4: work agent never injects conversation history / resume."""
    src = (PKG / "agents" / "work_agent.py").read_text(encoding="utf-8")
    assert "resume" not in src.lower()
