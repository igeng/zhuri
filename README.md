# zhuri (逐日)

> *Chasing the sun* — from the myth of Kuafu. `zhuri` relentlessly pursues a
> long-horizon goal, relay after relay, never stopping until done.

`zhuri` is a **framework-free multi-agent orchestrator** that implements the
**Deli_AutoResearch** protocol: a terminal-first driver (in the spirit of Claude
Code / OpenCode) that runs **long-horizon, zero-interaction** autonomous
research/coding tasks. It uses **no agent framework** (no crewai, langgraph,
langchain-agents, autogen, or llama-index agents). Agents are **isolated OS
processes** and all inter-agent communication happens **only through the
filesystem**.

See [`SPEC.md`](./SPEC.md) for the authoritative specification.
See [`TUTORIAL.md`](./TUTORIAL.md) for the complete user guide.
中文文档请参阅 [`README_zh.md`](./README_zh.md) 和 [`TUTORIAL_zh.md`](./TUTORIAL_zh.md)。

---

## What can zhuri do?

zhuri is a **general-purpose autonomous task runner**. It is not limited to
academic paper writing — any task that can be decomposed into iterative
research, analysis, or generation steps is a good fit:

| Task Type | Example |
|---|---|
| **Deep research survey** | "研究大模型 agent 强化学习，给我一份深度调研综述" |
| **Scientific paper writing** | Full pipeline: literature → structure → experiments → figures → peer review |
| **Code analysis & refactoring** | "Analyze this codebase and produce a refactoring plan with priorities" |
| **Technical documentation** | "Generate API reference docs for this project" |
| **Competitive analysis** | "Compare the top 5 vector databases and recommend one for our use case" |
| **Data analysis reports** | "Analyze the dataset and produce a statistical summary with visualizations" |
| **Literature review** | "Summarize the last 3 years of research on federated learning" |
| **Architecture design** | "Design a microservices architecture for an e-commerce platform" |

### Two execution modes

| Mode | Command | Behavior |
|---|---|---|
| **Direct** (one-shot) | `zhuri "prompt" --direct --yes` | Single LLM call → immediate result |
| **Iterative** (deep) | `zhuri "prompt" --yes` | Multi-iteration loop → deep, validated findings |
| **Iterative + Synthesis** | `zhuri "prompt" --yes --synthesize` | Iterations → final synthesized document |

**Direct mode** is best for quick questions or well-scoped tasks. **Iterative
mode** is best for complex, open-ended tasks that benefit from multiple
perspectives and structural diversity.

### Live monitoring & auto-stop

Entry A (`zhuri "prompt" --yes`) shows **real-time progress** — iteration count,
findings, stall signals, structural pivots — without requiring user interaction
(B1-safe). The orchestrator **auto-stops** escalated tasks that cannot improve
to avoid wasting API credits.

```bash
zhuri "prompt" --yes -v         # full detail: LLM calls, timings, token usage
zhuri "prompt" --yes             # one-line-per-iteration summary
zhuri "prompt" --yes --detach    # run in background (no monitor)
zhuri "prompt" --yes --no-search # skip ArXiv + Semantic Scholar search
```

### Academic paper search

Every work agent iteration pre-searches **ArXiv** and **Semantic Scholar** for
real, verifiable papers (both APIs are free, no auth required). Results are
injected into the LLM prompt so citations are based on actual publications.
Search failures are non-fatal. Disable with `--no-search`.

### Built-in task packs

`zhuri` ships with a pluggable task-pack system (`tasks/`). The first pack is
**paper-writing**, with 5 sub-skills:

| Sub-skill | Description |
|-----------|-------------|
| **Literature Survey** | 4-stage pipeline: Recall → LQS Scoring → A/B/C/D Classification → Venue Upgrade |
| **Structure & Logic** | Chapter architecture, paragraph patterns, MECE taxonomy, hedged claims |
| **Experiment Design** | Design → Execute(API/GPU) → Iterate(≤5) → Report(JSON) |
| **Figures & Tables** | Booktabs tables, vector figures, quality checklist, academic palette |
| **Peer Review** | 5 reviewer personas, median scoring, anti-inflation rules |

Each sub-skill encodes expert workflows directly into LLM prompts. The
orchestrator automatically routes reviewer-identified weaknesses to the
appropriate sub-skill. See [`SPEC-TODO.md`](./SPEC-TODO.md) for the roadmap.

---

## Quick Start (5 minutes)

### 1. Prerequisites

- **Python 3.10+** (check: `python --version`)
- **pip** (comes with Python)
- **Git Bash** (Windows) or any terminal (macOS/Linux)
- An LLM API key (DeepSeek / Qwen / Kimi / any OpenAI-compatible endpoint)

### 2. Install

```bash
# Clone or download the project
git clone git@github.com:igeng/zhuri.git
cd zhuri

# Install zhuri as a console script (editable mode for development)
pip install -e .

# Verify installation
zhuri --help
```

For development (pytest + coverage):
```bash
pip install -e '.[dev]'
```

After installation, the `zhuri` command is available globally in your terminal.

### 3. Configure an LLM provider

zhuri needs at least one LLM provider configured. Create a config file:

```bash
# Option A: project-local config
mkdir -p .zhuri
cp examples/config.toml .zhuri/config.toml

# Option B: global user config
mkdir -p ~/.config/zhuri
cp examples/config.toml ~/.config/zhuri/config.toml
```

Edit the config file and set your API key(s).

> ⚠️ **Security: never hardcode real API keys in config files.**
> Always use `${ENV_VAR}` syntax and keep real keys only in your shell profile.

For example, with DeepSeek:

```toml
[providers.deepseek]
type     = "openai_compat"
base_url = "https://api.deepseek.com/v1"
api_key  = "${DEEPSEEK_API_KEY}"
models   = ["deepseek-chat", "deepseek-reasoner"]

[agents.default]
provider = "deepseek"
model    = "deepseek-chat"
```

Then set the environment variables in your shell profile
(`~/.bashrc` / `~/.zshrc` / `~/.bash_profile`):

```bash
# Keep real keys ONLY in environment variables — never in files
export DEEPSEEK_API_KEY="sk-your-deepseek-key"
export QWEN_API_KEY="sk-your-qwen-key"
export MOONSHOT_API_KEY="sk-your-moonshot-key"
```

Reload your profile:
```bash
source ~/.bashrc    # or your respective profile file
```

Validate the configuration:
```bash
zhuri config check
zhuri doctor            # live auth probe per provider key
```

Config resolution order: `--config PATH` → `$ZHURI_CONFIG` → `./.zhuri/config.toml` → `~/.config/zhuri/config.toml`.

### 4. Start using zhuri

#### Fastest: direct mode (one-shot result)

```bash
zhuri "研究大模型 agent 强化学习，给我一份深度调研综述" --direct --yes
```

This produces the final document **immediately** in a single LLM call — no
iterations, no waiting. The result is printed to stdout and saved to
`state/deliverable.md`.

#### Deep mode: iterative research

```bash
zhuri "研究大模型 agent 强化学习，给我一份深度调研综述" --yes --synthesize
```

This runs multi-iteration research (exploring different structural axes), then
synthesizes all findings into a final document.

#### Interactive REPL (primary UX)

```bash
zhuri
```

Type a task in natural language and press Enter. zhuri will:
1. Synthesize a structured `task_spec.md` from your prompt
2. Show the spec for one-time confirmation
3. Launch the orchestrator and run **unattended** (zero-interaction)

---

## The three ways to start a task

All three converge on the same artifact: `state/task_spec.md` + the orchestrator.

### Entry A — one-shot ("prompt is the task")
```bash
zhuri "研究大模型 agent 强化学习，给我一份深度调研综述" --yes
```
Synthesizes a structured `task_spec.md`, shows it for **one** confirmation
(skipped with `--yes`), then runs unattended. Add `--direct` for immediate
one-shot result, `--synthesize` for a final document after iterations,
`--detach` to background it.

### Entry B — interactive REPL (primary UX)
```bash
zhuri
```
A long-lived TTY: type a task in natural language and press Enter — it
synthesizes the spec, then **immediately runs in the foreground**, streaming one
line per orchestrator iteration. Slash-commands are control-only: `/status`,
`/logs`, `/pause`, `/resume`, `/pivot <task>`, `/stop`, `/spec`, `/new "<prompt>"`,
`/config`, `/quit`.

### Entry C — config-file / scaffold (reproducible / CI)
```bash
zhuri init my-task --template paper-writing   # or: blank
#   edit my-task/state/task_spec.md
zhuri run ./                                    # orchestrate all tasks under a base dir
```

---

## Command summary

| Command | Purpose |
|---|---|
| `zhuri "<prompt>" [--dir D] [--yes] [--direct] [--synthesize] [--detach] [-v]` | Entry A: one-shot task |
| `zhuri` | Entry B: interactive REPL |
| `zhuri --verbose` or `zhuri -v` | Entry B: REPL with verbose logging |
| `zhuri --dir <path>` | Entry B: REPL in a specific working directory |
| `zhuri init <task-dir> [--template ...]` | Entry C: scaffold a task |
| `zhuri run <base-dir> [--interval 2h] [--max-iters N] [--once]` | Orchestrator loop |
| `zhuri synthesize <task-dir>` | Synthesize findings into a final document |
| `zhuri watchdog <base-dir> [--interval 1h]` | L1 durable patrol |
| `zhuri guard <base-dir>` | L0 resident guard |
| `zhuri work <task-dir> --direction "<d>" [--max-rounds 15] [--max-minutes 30]` | One work-agent iteration |
| `zhuri status <base-dir> [--watch] [--json]` | Read-only status |
| `zhuri logs <task-dir> [--source ...] [--level ...] [--follow]` | Read-only log tail |
| `zhuri config [get\|set\|path\|check]` | Manage providers/agents/keys |
| `zhuri doctor` | Validate env, provider auth, banned-deps |

Global flags: `-v` / `--verbose` enables real-time log output to stderr for any command.

Exit codes: `0` ok, `1` generic, `2` config, `3` provider/auth.

---

## REPL slash-commands

Once inside the zhuri REPL, you can use these slash-commands at any time:

| Command | Description |
|---|---|
| `/status` | Show status of all running tasks |
| `/logs [work\|orchestrator\|heartbeat]` | Tail the specified log stream |
| `/new "<prompt>"` | Start a new concurrent task |
| `/pause` | Pause orchestrator scheduling |
| `/resume` | Resume paused tasks |
| `/pivot <task>` | Force a structural pivot on the task |
| `/stop` | Stop all running tasks |
| `/spec` | Display the current task_spec.md |
| `/synthesize [task-dir]` | Synthesize findings into a final document |
| `/config` | Show current provider configuration |
| `/config verbose on\|off` | Toggle verbose (real-time log) mode |
| `/quit` | Exit zhuri |

These are **control-only** — they never violate B1 (zero-interaction on the run
path).

---

## The file-based message bus

Agents never share memory; they communicate **only via files**. Each task owns:

```
<task>/state/
├── task_spec.md            # goal / milestones / success criteria
├── progress.json           # iteration, status, stale_count, last_seen{...}
├── findings.jsonl          # append-only verifiable findings
├── directions_tried.json   # diversity basis (structural_axis per entry)
├── deliverable.md          # final synthesized document (after synthesis)
└── iteration_log.jsonl     # per-iteration summary
<task>/logs/
├── work.jsonl              # decisions tagged level=decision
├── orchestrator.jsonl
└── heartbeat.jsonl
```

Each iteration starts a **fresh session** injecting only curated state — `resume`
is forbidden (B4). Writes are atomic (temp-file + rename) under cross-process file
locks, so concurrent work agents on different tasks never corrupt state.

## Two-tier configuration

Configuration is split into **what endpoints exist** (`[providers.*]`) and **which
provider/model each agent role uses** (`[agents.*]`). This is how "different agent
→ different key/model" is achieved. v1 ships exactly one provider type:
`openai_compat` (OpenAI-compatible Chat Completions), which reaches Qwen, Kimi
(Moonshot), DeepSeek, or any local OpenAI-compatible server via `base_url`.

Resolution order for a role: `[agents.<role>]` → `[agents.default]` → error.
Sub-roles (e.g. `subagent.verification`) inherit from their parent role when
unset. Any string may interpolate `${ENV_VAR}`.

```toml
[providers.deepseek]
type     = "openai_compat"
base_url = "https://api.deepseek.com/v1"
api_key  = "${DEEPSEEK_API_KEY}"
models   = ["deepseek-chat", "deepseek-reasoner"]

[agents.default]
provider = "deepseek"
model    = "deepseek-chat"

[agents.work]            # strongest model for doing the work
provider = "qwen"
model    = "qwen-max"

[agents.review]          # different vendor on purpose; may use a model pool
provider = "kimi"
models   = ["kimi-k2-0905-preview", "moonshot-v1-128k"]
```

A ready-to-edit example lives at [`examples/config.toml`](./examples/config.toml).

---

## The 3-layer heartbeat watchdog

The business loop is itself unreliable, so an independent guardian layer watches
it. The three layers mutually check liveness:

- **L2** — each business loop (orchestrator + work) writes its own `last_seen`
  as the **first action** of every callback.
- **L1** — an hourly durable patrol: restarts a loop whose `last_seen` exceeds
  `interval × 3`; nudges a task stalled > 2h on a trailing question; escalates
  after 3 fruitless nudges.
- **L0** — a resident, session-independent guard: if the heartbeat is stale
  > 2h it spins up an emergency patrol.

A guardian may take only three actions on tasks that are not its own:
**check / restart / nudge** — never read findings or mutate results (B5).

---

## Development

```bash
pip install -e '.[dev]'              # install with dev dependencies
pytest                               # full suite
pytest --cov=zhuri --cov-report=term-missing
```

Guardrails enforced in CI: no banned agent-framework deps (A9), no source file
> 300 lines (EC1/A11), no blocking `input()` on the run path (B1/A12), the
watchdog's only cross-task surface is check/restart/nudge (B5), and coverage
floors (≥85% overall; ≥90% for `state/`, `orchestrator/`, `watchdog/`,
`config.py`).

---

## License

MIT
