# TUTORIAL.md — zhuri User Guide

This tutorial covers all zhuri features, commands, and configuration in detail.

---

## Table of Contents

1. [Installation & Verification](#1-installation--verification)
2. [Configuration](#2-configuration)
3. [Direct Mode](#3-direct-mode-one-shot)
4. [Launch Methods Quick Reference](#launch-methods-quick-reference)
5. [Iterative Mode (Deep Research)](#5-iterative-mode-deep-research)
6. [Interactive REPL](#6-interactive-repl)
7. [Task Scaffolding & Batch Runs](#7-task-scaffolding--batch-runs)
8. [Status & Logs](#8-status--logs)
9. [Synthesis (Findings → Document)](#9-synthesis-findings--document)
10. [Watchdog Configuration](#10-watchdog-configuration)
11. [Academic Search (ArXiv + Semantic Scholar)](#11-academic-search-arxiv--semantic-scholar)
12. [Paper-Writing Task Pack (Sub-skill System)](#12-paper-writing-task-pack-sub-skill-system)
13. [Typical Workflows](#13-typical-workflows)
14. [FAQ](#14-faq)

---

## 1. Installation & Verification

### Prerequisites

- **Python 3.10+** (`python --version`)
- **pip** (included with Python)
- **Git Bash** (Windows) or any terminal (macOS/Linux)
- An LLM API key (DeepSeek / Qwen / Kimi / any OpenAI-compatible endpoint)

### Install

```bash
git clone git@github.com:igeng/zhuri.git
cd zhuri

# Install in editable mode (recommended for development)
pip install -e .

# With dev dependencies (pytest + coverage)
pip install -e '.[dev]'

# Verify
zhuri --help
```

### Quick Config

```bash
mkdir -p ~/.config/zhuri
cp examples/config.toml ~/.config/zhuri/config.toml
# Edit the file and set your API keys (use ${ENV_VAR} syntax — never hardcode!)
```

> **Security:** Always use `${ENV_VAR}` references in config files. Keep real API keys
> only in your shell profile (`~/.bashrc` / `~/.zshrc`):
> ```bash
> export DEEPSEEK_API_KEY="sk-your-deepseek-key"
> export QWEN_API_KEY="sk-your-qwen-key"
> export MOONSHOT_API_KEY="sk-your-moonshot-key"
> ```

Validate:
```bash
zhuri config check     # syntax + provider validation
zhuri doctor           # live API key probe (use --offline to skip)
```

---

## 2. Configuration

zhuri uses a two-tier configuration model:

- **`[providers.*]`** — what LLM endpoints exist, each with its own key
- **`[agents.*]`** — which provider/model each agent role uses

Example (`~/.config/zhuri/config.toml`):

```toml
[providers.deepseek]
type     = "openai_compat"
base_url = "https://api.deepseek.com/v1"
api_key  = "${DEEPSEEK_API_KEY}"
models   = ["deepseek-v4-flash", "deepseek-v4-pro"]

[agents.default]
provider = "deepseek"
model    = "deepseek-v4-flash"

[agents.work]           # strongest model for research
provider = "deepseek"
model    = "deepseek-v4-pro"

[agents.review]         # different vendor for independent review
provider = "kimi"
model    = "kimi-k2.5"
```

### Role Resolution

`[agents.<role>]` → `[agents.default]` → error. Sub-roles (e.g. `subagent.verification`) inherit from their parent when unset.

### View Effective Config

```bash
zhuri config get --effective         # all roles
zhuri config get --effective --role work  # single role
zhuri config get --effective --json  # machine-readable
```

---

## 3. Direct Mode (One-Shot)

Single LLM call → immediate result. Best for quick, well-scoped questions.

```bash
zhuri "your prompt" --direct --yes
```

Output: stdout + `state/deliverable.md`.

---

## Launch Methods Quick Reference

zhuri has 5 launch methods. **The end goal is always the synthesized document `deliverable.md`.**

| Method | Command | Confirm? | How to Get Final Document |
|--------|---------|----------|---------------------------|
| **REPL Interactive** | `zhuri` → `❯ paste task` | spec + y/N | In REPL: `/synthesize` |
| **Direct Run** | `zhuri "task"` | spec + y/N | `zhuri synthesize .zhuri/tasks/<task-id>` |
| **Skip Confirm** | `zhuri "task" --yes` | None | `zhuri synthesize .zhuri/tasks/<task-id>` |
| **Background** | `zhuri "task" --yes --detach` | None | `zhuri status` wait → `zhuri synthesize <dir>` |
| **BG + Auto-Synth** | `zhuri "task" --yes --detach --synthesize` | None | Auto: `state/deliverable.md` |

### Flag Reference

| Flag | Effect |
|------|--------|
| (none) | Show spec for one-time confirmation (B1-exempt), then foreground run |
| `--yes` | Skip confirmation, start immediately (zero-interaction) |
| `--direct` | Single LLM call, no iterations |
| `--detach` | Background execution, terminal returns immediately |
| `--synthesize` | Auto-merge all findings into deliverable.md after iterations |
| `--max-iters N` | Max orchestrator ticks (default: 30; 0 = unlimited) |
| `--interval N` | Seconds between ticks (default: 5s foreground, 2h cron) |
| `--no-search` | Skip ArXiv + Semantic Scholar pre-search |
| `-v` / `--verbose` | Full LLM call logs to stderr |

### Runtime Thresholds

zhuri has sane defaults to prevent infinite runs while allowing deep exploration:

| Threshold | Value | What Happens |
|-----------|-------|-------------|
| Pivot | stale ≥ 2 | Force structural axis change |
| Escalate | stale ≥ 4 | Flag for human attention |
| Auto-stop | stale ≥ 8 | Stop task (avoid burning API credits) |
| Entry A default max ticks | 30 | Orchestrator stops after 30 ticks (override with `--max-iters 0`) |
| Work agent cap | 15 rounds / 30 min | Per work agent session |

View in REPL: `/limits`. Adjust in REPL: `/set-iters N`.

### Output Location

```
<working-dir>/.zhuri/tasks/<task-id>/state/
├── task_spec.md          # goal / milestones / success criteria
├── findings.jsonl         # all intermediate findings (append-only)
├── deliverable.md         # ★ final synthesized document
├── progress.json          # iteration count, status, stale_count
├── directions_tried.json  # structural axes explored
└── iteration_log.jsonl    # per-iteration summary
```

---

## 5. Iterative Mode (Deep Research)

Multi-iteration exploration across different structural axes. Best for complex,
open-ended tasks.

### Basic Usage

```bash
zhuri "your research topic" --yes          # default: continuous iterations
zhuri "your topic" --yes --max-iters 5     # max 5 ticks
zhuri "your topic" --yes --once            # single tick
zhuri "your topic" --yes --detach          # background
zhuri "your topic" --yes --synthesize      # auto-merge at end
```

### Live Progress Output

Entry A auto-enters **monitor mode** (B1-safe: display only, no interaction):

```
  [search] querying ArXiv + Semantic Scholar: large language model HPC post-training...
  [search] found 15 papers
  [orch] > spawning work agent for task-001  direction='method_comparison'
  [work] > round 1/15  sending to deepseek-v4-pro  (elapsed=0s)...
  [work] ok  round 1/15  557 chars  19047ms  findings=2
  [work] > round 2/15  sending to deepseek-v4-pro  (elapsed=19s)...
  [work] ok  round 2/15  1328 chars  18985ms  findings=3
  [work] DONE signal received
  [orch] ok  work agent done  rc=0  new_findings=13
  [running ] iter=1  findings=13  gain
```

### Iteration Lifecycle

| Status | Trigger | Meaning |
|--------|---------|---------|
| `running` | Default | Active, finding results |
| `pivoting` | stale ≥ 2 | Forced structural axis change |
| `escalated` | stale ≥ 4 | Flagged for human attention |
| `done` | Terminal | Task complete, orchestrator stops |
| auto-stop | escalated + stale ≥ 8 | No improvement → stop to save API credits |

### Verbose Mode

```bash
zhuri "task" --yes -v     # Full LLM call details: timing, tokens, model routing
```

In REPL: `/config verbose on` / `/config verbose off`

---

## 6. Interactive REPL

### Launch

```bash
zhuri                    # default working directory
zhuri --dir ~/projects   # custom directory
```

### Submit a Task

At the `❯` prompt, type or paste your research question and press Enter.
**Multi-line paste is supported** — paste entire paragraphs including blank
lines; all content is captured into a single prompt.

### Slash Commands

| Command | Description |
|---------|-------------|
| `/status` | Show all task status |
| `/logs [work\|orchestrator\|heartbeat]` | Tail specified log stream |
| `/new "prompt"` | Start a new concurrent task |
| `/pause` | Pause orchestrator scheduling |
| `/resume` | Resume paused scheduling |
| `/pivot [task-id]` | Force structural pivot |
| `/stop` | Stop all running tasks |
| `/spec` | Display current task_spec.md |
| `/synthesize [task-id]` | Merge findings into deliverable.md |
| `/config` | Show provider configuration |
| `/config verbose on\|off` | Toggle verbose logging |
| `/help` | Show all commands |
| `/set-iters N` | Set foreground max iterations (0=unlimited) |
| `/limits` | Show all threshold values |
| `/quit` | Exit REPL |

---

## 7. Task Scaffolding & Batch Runs

### Scaffold a Task (Entry C)

```bash
zhuri init my-task --template paper-writing    # or: blank
# edit my-task/state/task_spec.md
zhuri run ./                                     # orchestrate all tasks
```

### Batch Orchestration

```bash
zhuri run <base-dir> --interval 2h --max-iters 10
zhuri run <base-dir> --once          # single tick
```

---

## 8. Status & Logs

```bash
# Status
zhuri status <base-dir>              # one-shot
zhuri status <base-dir> --watch      # live refresh (Ctrl+C to stop)
zhuri status <base-dir> --json       # machine-readable

# Logs
zhuri logs <task-dir> --source work              # work agent log
zhuri logs <task-dir> --source orchestrator      # orchestrator log
zhuri logs <task-dir> --level decision           # decisions only
zhuri logs <task-dir> --tail 100                 # last 100 lines
```

---

## 9. Synthesis (Findings → Document)

Merge accumulated findings into a final document:

```bash
# CLI
zhuri synthesize .zhuri/tasks/task-0001baf93b2d

# REPL
❯ /synthesize                      # latest task
❯ /synthesize task-0001baf93b2d    # specific task
```

Output: stdout + `state/deliverable.md`.

---

## 10. Watchdog Configuration

zhuri has a 3-layer heartbeat watchdog to survive process crashes and stalls:

| Layer | Command | Role |
|-------|---------|------|
| L0 | `zhuri guard <base-dir>` | Resident session-independent guardian |
| L1 | `zhuri watchdog <base-dir>` | Hourly patrol: restart loops, nudge stalled tasks |
| L2 | Built-in | Each callback writes `last_seen` as its first action |

The watchdog may only take three actions on tasks it does not own:
**check / restart / nudge** (B5: guardian/worker separation).

---

## 11. Academic Search (ArXiv + Semantic Scholar)

By default, every work agent iteration pre-searches ArXiv and Semantic Scholar
for real, verifiable papers. Results are injected into the LLM prompt so
citations are based on actual publications, not model training data.

### How It Works

1. Before the first LLM round, zhuri derives a search query from your task
2. Queries ArXiv API + Semantic Scholar API (both free, no auth required)
3. Merges and deduplicates results
4. Injects a formatted reference block into the work agent prompt
5. Search failures are non-fatal — logged as warnings, execution continues

### Disable Search

```bash
zhuri "task" --yes --no-search     # skip search (pure LLM mode)
ZHURI_NO_SEARCH=1 zhuri "task" --yes  # env var override
```

Search is automatically skipped during test runs.

---

## 12. Paper-Writing Task Pack (Sub-skill System)

zhuri ships with a pluggable task-pack system (`tasks/`). The first complete
implementation is the **paper-writing pack** with 5 sub-skills:

| Sub-skill | Direction Key | Workflow |
|-----------|--------------|----------|
| **Literature Survey** | `subskill:literature` | 4-stage: Recall → LQS Scoring → A/B/C/D Classification → Venue Upgrade |
| **Paper Structure** | `subskill:structure` | Chapter architecture + paragraph patterns + MECE taxonomy + hedged claims |
| **Experiment Design** | `subskill:experiment` | Design(hypothesis)→Execute(API/GPU)→Iterate(≤5)→Report(JSON) |
| **Figures & Tables** | `subskill:figures` | Booktabs tables + vector figures + quality checklist + academic palette |
| **Peer Review** | `subskill:review` | 5 reviewer personas → median scoring → weakness routing → anti-inflation |

### Automatic Feedback Loop

Reviewer-identified weaknesses are **automatically routed** to the responsible sub-skill:

```
Review agent output → Weakness routing table → Inject direction → Next work agent
                                              ↓
"Missing experiments" → subskill:experiment → Experiment Design skill
"Insufficient citations" → subskill:literature → Literature Survey skill
```

### LQS Scoring (Literature Survey)

The Literature Survey sub-skill uses a 5-dimension weighted scoring system:

| Dimension | Weight | Scoring |
|-----------|--------|---------|
| Recency | 30% | ≤6 months=10, ≤1 year=8 |
| Citation Impact | 25% | cites/month ≥50=10 |
| Venue | 20% | Top-tier=10, Strong=7 |
| Institution | 10% | Top lab=10 |
| Acceptance | 15% | Published=10 |

LQS ≥ 7.0 → must-cite, 5.0–7.0 → conditional, <5.0 → drop.

### Extending with Custom Task Packs

Implement `TaskPack` and `SubSkill` from `tasks/base.py`:

```python
from zhuri.tasks.base import TaskPack, SubSkill, SubSkillContext

class MyCodeReviewPack(TaskPack):
    name = "code_review"
    sub_skills = {"security": SecurityReviewSkill(), ...}
    ...
```

---

## 13. Typical Workflows

### Quick Research Survey

```bash
zhuri "summarize recent advances in federated learning" --direct --yes
```

### Deep Paper Writing

```bash
zhuri "write a survey on LLM post-training for HPC..." --yes --synthesize
```

### Background Long-Running Task

```bash
zhuri "comprehensive literature review on reinforcement learning" --yes --detach --synthesize

# Check progress periodically
zhuri status .zhuri/tasks/
zhuri logs .zhuri/tasks/task-xxx --source work --tail 20
```

### REPL Multi-Task Session

```
❯ research vector databases for RAG applications
(tasks runs in foreground, results stream to terminal)

❯ /new "compare PyTorch vs JAX for scientific computing"
(second task starts concurrently)

❯ /status
(after both complete)
❯ /synthesize
❯ /quit
```

---

## 14. FAQ

### Q: Direct mode vs Iterative mode?

- **Direct**: quick questions, well-scoped tasks, single-answer results
- **Iterative**: complex research, open-ended exploration, multi-perspective analysis

### Q: `zhuri: command not found`?

Re-run `pip install -e .` and verify Python Scripts is in your PATH.

### Q: `config error: config file not found`?

Create the config at `.zhuri/config.toml` or `~/.config/zhuri/config.toml`.

### Q: `provider error: auth failed`?

Check environment variables: `echo $DEEPSEEK_API_KEY`. Run `zhuri doctor` for diagnostics.

### Q: Task seems stuck or not making progress?

Check status: `zhuri status <base-dir>`. If `stale_count` is high, the task may have exhausted easy findings. The orchestrator auto-stops escalated tasks after 8 consecutive stalls to save API credits.

### Q: How do I stop a running task?

- Foreground: `Ctrl+C`
- Background: `zhuri status` to find the task, then kill the process
- REPL: `/stop`

### Q: Can I use multiple providers?

Yes. Each agent role can route to a different provider/model. The `review` role
should use a different vendor than `work` for independent evaluation.

### Q: Are my API keys safe?

zhuri never stores API keys in project files. Always use `${ENV_VAR}` syntax in
config files and keep real keys only in your shell profile. The project `.gitignore`
excludes all credential files.
