<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue?style=flat-square" alt="version">
  <img src="https://img.shields.io/badge/python-3.10+-green?style=flat-square" alt="python">
  <img src="https://img.shields.io/badge/license-MIT-orange?style=flat-square" alt="license">
  <img src="https://img.shields.io/badge/tests-184%20passed-brightgreen?style=flat-square" alt="tests">
  <img src="https://img.shields.io/badge/framework-free-red?style=flat-square" alt="zero framework">
</p>

<h1 align="center">zhuri (逐日)</h1>

<p align="center">
  <em>Chasing the sun — from the myth of Kuafu.</em><br>
  <em>A framework-free multi-agent orchestrator for long-horizon autonomous research.</em>
</p>

<p align="center">
  <strong>Start it. Walk away. Come back to a finished paper.</strong>
</p>

---

## What is zhuri?

`zhuri` is a **framework-free multi-agent orchestrator** implementing the
**Deli_AutoResearch** protocol: a terminal-first driver (in the spirit of Claude
Code / OpenCode) that runs **long-horizon, zero-interaction** autonomous
research and coding tasks.

> *"It ships no executable code; it prescribes battle-tested conventions."*
> — Deli_AutoResearch SKILL.md

### Why zhuri?

| Problem | zhuri's Solution |
|---------|-----------------|
|  Cognitive loops (repeating same directions) | Direction diversity + forced structural pivots |
|  Silent stalling (looks alive, does nothing) | 3-layer heartbeat watchdog (L0/L1/L2) |
|  Runtime fragility (crash = lost progress) | File-based persistence, no resume |
|  LLM hallucinated citations | Real ArXiv + Semantic Scholar search |
|  Infinite API credit burn | Auto-stop when task cannot improve |

### Design stance

- **No agent framework** — no crewai, langgraph, langchain, autogen, llama-index
- **File-system communication** — agents are isolated OS processes
- **Zero interaction** — once confirmed, never asks again (B1)

See [`SPEC.md`](./SPEC.md) for the authoritative specification.
See [`TUTORIAL.md`](./TUTORIAL.md) for the complete user guide.
中文文档请参阅 [`README_zh.md`](./README_zh.md) 和 [`TUTORIAL_zh.md`](./TUTORIAL_zh.md)。

---

## Quick Start

### 1. Install

```bash
git clone git@github.com:igeng/zhuri.git
cd zhuri
pip install -e .                # editable mode (recommended)
pip install -e '.[dev]'         # with pytest + coverage
```

### 2. Configure

```bash
mkdir -p ~/.config/zhuri
cp examples/config.toml ~/.config/zhuri/config.toml
```

Edit and set your API keys. **Always use `${ENV_VAR}` — never hardcode keys.**

```toml
[providers.deepseek]
type     = "openai_compat"
base_url = "https://api.deepseek.com/v1"
api_key  = "${DEEPSEEK_API_KEY}"
models   = ["deepseek-v4-flash", "deepseek-v4-pro"]

[agents.work]
provider = "deepseek"
model    = "deepseek-v4-pro"
```

Set keys in your shell profile (`~/.bashrc`):

```bash
export DEEPSEEK_API_KEY="sk-your-key"
export MOONSHOT_API_KEY="sk-your-key"
```

### 3. Validate

```bash
zhuri config check              # syntax + provider check
zhuri doctor                    # live API key probe
```

### 4. Run

```bash
zhuri "your research question" --yes                     # run with live monitor
zhuri "your research question" --yes --synthesize         # auto-merge at end
zhuri "your research question" --yes --detach --synthesize  # background
zhuri                                                      # interactive REPL
```

---

## Launch Methods

| <div style="width:80px">Method</div> | Command | Use Case |
|:---|---------|----------|
|  **Quick** | `zhuri "q" --direct --yes` | Single LLM call, instant result |
|  **Foreground** | `zhuri "task" --yes` | Live monitor, max 30 ticks |
|  **Background** | `zhuri "task" --yes --detach` | Hours/days, check with `zhuri status` |
|  **Auto-synth** | `zhuri "task" --yes --detach --synthesize` | Background + auto deliverable |
|  **REPL** | `zhuri` | Interactive session, multi-task management |

**Where's my result?**
`.zhuri/tasks/<task-id>/state/deliverable.md`

---

## Architecture

```
┌── Orchestrator (monitor → detect stalls → inject direction) ──┐
│  • Direction diversity — never repeat the same structural axis │
│  • Auto-pivot on stall (≥2) → escalate (≥4) → auto-stop (≥8) │
│  • Review→weakness→sub-skill feedback loop                    │
└────┬─────────────┬─────────────┬────────────┘
  [Task A]      [Task B]      [Task C]   ← isolated subprocesses

┌── Heartbeat Watchdog (3 layers) ──┐
│ L0  Resident guard (no session)   │
│ L1  Hourly patrol (restart/nudge) │
│ L2  Business loop self-check      │
└───────────────────────────────────┘

┌── Work Agent (per-iteration) ──┐
│ 1. Pre-search ArXiv + Semantic Scholar
│ 2. LLM rounds (≤15 / ≤30 min)
│ 3. Append findings to state/
│ 4. Exit — process is disposable
└────────────────────────────────┘
```

---

## Key Features

###  Academic Paper Search

Every work agent iteration pre-searches **ArXiv** + **Semantic Scholar**
for real, verifiable papers (both APIs free, no auth). Citations are based on
actual publications, not model training data. Disable with `--no-search`.

###  Sub-skill Task Packs

Built-in paper-writing pack with 5 sub-skills, each encoding expert workflows:

| Sub-skill | Direction | Pipeline |
|-----------|-----------|----------|
|  Literature | `subskill:literature` | Recall → LQS scoring → A/B/C/D classify → venue upgrade |
|  Structure | `subskill:structure` | Chapter architecture + paragraph patterns + MECE taxonomy |
|  Experiment | `subskill:experiment` | Design → Execute(API/GPU) → Iterate(≤5) → Report |
|  Figures | `subskill:figures` | Booktabs tables + vector figures + quality checklist |
|  Review | `subskill:review` | 5 personas → median score → weakness routing → anti-inflation |

###  Live Monitoring & Auto-Stop

Real-time terminal output during execution. Orchestrator auto-stops
escalated tasks to prevent API waste:

| Threshold | Value | Action |
|-----------|-------|--------|
| Pivot | stale ≥ 2 | Force structural axis change |
| Escalate | stale ≥ 4 | Flag for human attention |
| Auto-stop | stale ≥ 8 | Stop — no more progress possible |

###  REPL with Multi-line Paste

```
❯ Write a comprehensive survey on LLM post-training for HPC...

❯ /status          # show all tasks
❯ /synthesize      # merge findings → deliverable.md
❯ /limits          # view all thresholds
❯ /set-iters 0     # unlimited iterations
❯ /quit
```

---

## Command Reference

| Command | Purpose |
|---------|---------|
| `zhuri "prompt" [--yes] [--direct] [--synthesize] [--detach] [-v]` | Entry A: one-shot task |
| `zhuri` | Entry B: interactive REPL (primary UX) |
| `zhuri init <dir> [--template ...]` | Entry C: scaffold a task |
| `zhuri run <dir> [--interval 2h] [--max-iters N] [--once]` | Orchestrator loop |
| `zhuri synthesize <task-dir>` | Merge findings → deliverable.md |
| `zhuri watchdog <dir> [--interval 1h]` | L1 hourly patrol |
| `zhuri guard <dir>` | L0 resident guard |
| `zhuri work <task-dir> --direction "..."` | Single work-agent iteration |
| `zhuri status <dir> [--watch] [--json]` | Read-only status |
| `zhuri logs <task-dir> [--source ...] [--follow]` | Read-only log tail |
| `zhuri config [get|set|path|check]` | Manage providers/agents/keys |
| `zhuri doctor` | Validate env, auth, deps |

---

## What can zhuri do?

| Task Type | Example |
|-----------|---------|
|  Deep research survey | "Survey LLM agent RL, give me a comprehensive review" |
|  Scientific paper writing | Full pipeline: literature → structure → experiments → review |
|  Code analysis | "Analyze this codebase and produce a refactoring plan" |
|  Technical docs | "Generate API reference docs for this project" |
|  Competitive analysis | "Compare top 5 vector databases, recommend one" |
|  Data analysis | "Analyze dataset, produce statistical summary with visuals" |
|  Architecture design | "Design microservices architecture for e-commerce" |

---

## Configuration

Two-tier model: **providers** (what endpoints exist) + **agents** (which role uses what).

```toml
[providers.deepseek]
type     = "openai_compat"
base_url = "https://api.deepseek.com/v1"
api_key  = "${DEEPSEEK_API_KEY}"
models   = ["deepseek-v4-flash", "deepseek-v4-pro"]

[agents.work]       # strongest model for research
provider = "deepseek"
model    = "deepseek-v4-pro"

[agents.review]     # different vendor (anti-inflation)
provider = "kimi"
model    = "kimi-k2.5"
```

Resolution: `[agents.<role>]` → `[agents.default]` → error.

---

## State Files

```
<task>/state/
├── task_spec.md            # goal / milestones / success criteria
├── progress.json           # iteration, status, stale_count, last_seen
├── findings.jsonl          # append-only verifiable findings
├── directions_tried.json   # diversity basis (structural_axis per entry)
├── deliverable.md          # ★ final synthesized document
└── iteration_log.jsonl     # per-iteration summary
<task>/logs/
├── work.jsonl              # decisions tagged level=decision
├── orchestrator.jsonl
└── heartbeat.jsonl
```

---

## Development

```bash
pip install -e '.[dev]'
pytest                               # 184 tests
pytest --cov=zhuri --cov-report=term-missing
```

Guardrails: no agent-framework deps (A9), files ≤ 300 lines (EC1),
no blocking input on run path (B1/A12), coverage ≥ 85%.

---

## License

MIT © zhuri contributors

---

<p align="center">
  <sub>☀️ chasing the sun ☀️</sub>
</p>
