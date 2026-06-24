"""Tests for the direct synthesis agent (zhuri/agents/synthesize.py)."""
from __future__ import annotations

from zhuri.agents.synthesize import synthesize_document
from zhuri.config import load_config_str
from zhuri.providers.fake import FakeProvider
from zhuri.providers.registry import Registry
from zhuri.state.models import Finding, Progress
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

SYNTH_OUTPUT = (
    "# Research Survey: Agent RL\n\n"
    "## Executive Summary\nThis survey covers...\n\n"
    "## Key Findings\n- Finding A\n- Finding B\n\n"
    "## Conclusion\nIn summary...\n"
)


def _reg(provider):
    return Registry(load_config_str(CFG), factory=lambda eff: provider)


def _setup_task(tmp_path, findings_count=5):
    """Create a task dir with spec and findings."""
    task_dir = tmp_path / "task-synth"
    store = TaskStore(task_dir)
    store.ensure_dirs()
    store.write_task_spec(
        "# Goal\nResearch agent RL\n\n## Milestones\n1. Survey\n\n"
        "## Success criteria\n- Comprehensive report\n"
    )
    store.write_progress(Progress.new(task_dir.name))
    for i in range(findings_count):
        store.append_finding(Finding(
            claim=f"claim_{i}",
            evidence=f"evidence_{i}",
            iteration=i + 1,
            verifiable=True,
        ))
    return task_dir


def test_synthesize_produces_document(tmp_path):
    """Synthesis agent produces a deliverable from findings."""
    task_dir = _setup_task(tmp_path)
    reg = _reg(FakeProvider(default=SYNTH_OUTPUT))
    doc = synthesize_document(task_dir, reg)
    assert doc == SYNTH_OUTPUT
    # Deliverable is written to state.
    deliverable = (task_dir / "state" / "deliverable.md").read_text(encoding="utf-8")
    assert deliverable == SYNTH_OUTPUT


def test_synthesize_sets_status_done(tmp_path):
    """Synthesis marks task as done."""
    task_dir = _setup_task(tmp_path)
    reg = _reg(FakeProvider(default=SYNTH_OUTPUT))
    synthesize_document(task_dir, reg)
    store = TaskStore(task_dir)
    progress = store.read_progress()
    assert progress.status == "done"


def test_synthesize_empty_findings_returns_empty(tmp_path):
    """Synthesis with no findings returns empty string."""
    task_dir = tmp_path / "task-empty"
    store = TaskStore(task_dir)
    store.ensure_dirs()
    store.write_task_spec("# Goal\nTest\n\n## Milestones\n1. a\n\n## Success criteria\n- b\n")
    store.write_progress(Progress.new(task_dir.name))
    reg = _reg(FakeProvider(default=SYNTH_OUTPUT))
    doc = synthesize_document(task_dir, reg)
    assert doc == ""


def test_synthesize_includes_all_findings_in_prompt(tmp_path):
    """The synthesis prompt includes all accumulated findings."""
    task_dir = _setup_task(tmp_path, findings_count=3)
    provider = FakeProvider(default=SYNTH_OUTPUT)
    reg = _reg(provider)
    synthesize_document(task_dir, reg)
    # Check the prompt sent to the provider contains all findings.
    assert len(provider.calls) == 1
    user_msg = provider.calls[0]["messages"][0]["content"]
    assert "claim_0" in user_msg
    assert "claim_1" in user_msg
    assert "claim_2" in user_msg


def test_synthesize_cli_subcommand(tmp_path, monkeypatch):
    """The 'synthesize' CLI subcommand works end-to-end."""
    task_dir = _setup_task(tmp_path)
    # Write a config file so CLI can load it.
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CFG, encoding="utf-8")

    from zhuri.cli import main

    exit_code = main(["--config", str(cfg_path), "synthesize", str(task_dir)],
                     provider_factory=lambda eff: FakeProvider(default=SYNTH_OUTPUT))
    assert exit_code == 0


def test_direct_generate(tmp_path):
    """Direct mode produces a deliverable without needing findings."""
    from zhuri.agents.synthesize import direct_generate

    task_dir = tmp_path / "task-direct"
    store = TaskStore(task_dir)
    store.ensure_dirs()
    store.write_progress(Progress.new(task_dir.name))
    reg = _reg(FakeProvider(default=SYNTH_OUTPUT))
    doc = direct_generate(task_dir, "research agent RL", reg)
    assert doc == SYNTH_OUTPUT
    assert (task_dir / "state" / "deliverable.md").read_text(encoding="utf-8") == SYNTH_OUTPUT
    assert store.read_progress().status == "done"


def test_direct_cli_flag(tmp_path):
    """Entry A --direct flag produces output without running iterations."""
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CFG, encoding="utf-8")

    from zhuri.cli import main

    exit_code = main(
        ["research RL", "--config", str(cfg_path), "--dir", str(tmp_path),
         "--yes", "--direct"],
        provider_factory=lambda eff: FakeProvider(default=SYNTH_OUTPUT),
    )
    assert exit_code == 0
