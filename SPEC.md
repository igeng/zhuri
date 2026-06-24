# SPEC.md — `zhuri` (逐日) CLI

> Spec-Driven Development (SDD) specification for a **framework-free multi-agent
> orchestrator** that implements the **Deli_AutoResearch** protocol.
>
> **Authoritative skill source (MUST be honored):**
> - https://victorchen96.github.io/auto_research/framework.html
> - https://victorchen96.github.io/auto_research/framework.html#fullmd  (the full `SKILL.md`)
> - Reference task pack: https://victorchen96.github.io/auto_research/skill/paper-writing.html
>
> **Name.** `zhuri` (逐日, "chasing the sun" — from the myth of Kuafu) evokes the
> system's core nature: relentlessly pursuing a long-horizon goal, relay after
> relay, never stopping until done.
>
> **Repository independence.** This specification is **not tied to any specific
> Git repository, owner, or hosting account.** Do not hardcode, assume, or
> reference any particular repo. The implementing agent targets whatever
> repository it is told to use at build time.
>
> This document is the **single source of truth**. The implementing agent MUST
> treat every MUST / MUST NOT / SHALL clause as a hard acceptance criterion.
> Where this spec and intuition disagree, this spec wins. Open questions are in
> §13 and MUST be resolved before coding the affected module.

---

## 0. How to Build This (process rules for the implementing agent)

### 0.1 Testing Discipline (NON-NEGOTIABLE — applies to EVERY part)
This is an SDD project. **No feature is "done" until it has comprehensive,
passing tests.** The implementing agent MUST:

1. **Test-as-you-go.** After completing *each* functional unit (a module, a
   command, a sub-skill, a watchdog layer), the agent MUST **immediately write
   and run tests for that unit** before moving on. Do NOT batch testing to the
   end. (This mirrors SKILL.md EC3: *validation must run between iterations.*)
2. **Per-section "Required Tests".** Many sections below contain a **`Required
   Tests`** subsection. Those are the *minimum* tests for that unit; the agent
   SHOULD add more for edge cases it discovers.
3. **Milestone gates (§16).** Each milestone has an explicit **exit test gate**.
   The agent MUST NOT start milestone _N+1_ until milestone _N_'s gate is green.
4. **Coverage floor.** Line coverage MUST be **≥ 85%** overall and **≥ 90%** for
   `state/`, `orchestrator/`, `watchdog/`, and `config.py` (the correctness-
   critical core). CI MUST fail below these floors.
5. **Test types required:** unit tests, **multi-process/integration** tests
   (real subprocess spawning for work agents and watchdog), config-resolution
   tests, and **guardrail/static** tests (banned-deps, ≤300-line files, no
   interactive blocking on the run path).
6. **Determinism.** Tests MUST NOT call real LLM endpoints; use a **fake
   `openai_compat` provider** (record/replay or stub). Any nondeterminism
   (pool rotation, ids, timestamps) MUST be seedable/injectable.
7. **Green-before-commit.** Every commit/PR MUST have the full test suite green
   and coverage floors met. A change that lowers coverage below the floor or
   weakens B1–B5 / EC1–EC6 fails review.

### 0.2 Definition of "complete" for any task
A unit is complete only when: code + `Required Tests` written + tests pass +
coverage floor held + relevant acceptance criteria (§14) demonstrably satisfied.

---

## 1. Purpose & Scope

### 1.1 Goal
Implement `zhuri`, a Python **CLI** that runs **long-horizon (days→weeks),
zero-interaction autonomous research/coding tasks** as a **multi-agent system**,
**without any agent framework** (NO crewai, NO langgraph, NO langchain-agents,
NO autogen, NO llama-index agents). The runtime model and UX mirror
**Claude Code / OpenCode**: a terminal-first orchestrator that spawns isolated
agent sessions and persists all state to files.

### 1.2 In scope
- Orchestrator loop, work-agent execution, 3-layer heartbeat watchdog.
- File-based state system (`state/`) and structured logs (`logs/`).
- Stall detection + forced structural pivoting + direction-diversity enforcement.
- Subagent scheduling patterns A/B/C/D.
- A pluggable LLM provider layer called **directly** (no agent framework), with
  two-tier `[providers.*]` / `[agents.*]` configuration (§10, §10A).
- Three task-input entries (one-shot / REPL / config-file), REPL primary (§4).
- A reference task pack: the **Scientific Paper Writing** skill group (§11).
- A test suite that satisfies the Testing Discipline (§0.1) end to end.

### 1.3 Out of scope (v1)
- GUI / web UI.
- Distributed multi-machine scheduling (single host only in v1).
- Training models; we only *call* LLM/inference APIs.
- Provider types other than `openai_compat` (OpenAI/Anthropic/local presets are
  deferred to a later version — see §10.2).

### 1.4 Non-negotiable design stance
The protocol is **convention, not a library** (SKILL.md: *"ships no executable
code; prescribes battle-tested conventions"*). Inter-agent communication happens
**only through the filesystem**. Agents are **isolated OS processes**, never
threads sharing Python objects, and never resumed sessions.

---

## 2. Definitions

| Term | Meaning |
|------|---------|
| **Orchestrator** | Long-lived driver — **current session OR durable cron** (SKILL.md §3). Monitors `state/`, detects stalls, injects directions, launches work agents. Does NOT do the task work. |
| **Work agent** | A **fresh OS process** spawned per iteration to do one bounded chunk of work. Reads curated state files, writes findings back. Never resumed. |
| **Subagent** | A short-lived agent launched by a work agent or orchestrator for a scoped deliverable (patterns A/B/C/D). |
| **Heartbeat watchdog** | Independent guardian. Three layers L0/L1/L2 that mutually check liveness. |
| **Iteration** | One orchestrator-driven unit of progress for a task. |
| **Direction** | A structural hypothesis/approach for an iteration; must differ from all tried directions. |
| **Stall** | An iteration with 0 new findings or a metric drop. |
| **Pivot** | Changing a *structural* constraint (not a tactical parameter) after repeated stalls. |
| **Agent role** | A named consumer of an LLM (orchestrator / spec / work / review / subagent.*), each routable to its own provider+model+key (§10A). |

---

## 3. Behavioral Constraints (HARD RULES — verbatim intent from SKILL.md §2)

There are **exactly five** behavioral constraints in the skill. They MUST be
enforced at the **code level**, not via prompt text alone — SKILL.md's own limits
note: *"Separation of duties relies on protocol constraints, not model
self-discipline; removing the constraints brings overstepping behavior back."*

- **B1 — Zero interaction.** During a run the system MUST NOT prompt the user:
  no plan-mode pause, no "should I proceed?", no ending a turn on a question.
  Ambiguity MUST be resolved autonomously and recorded to a state file.
  - *Exemption:* the one-time **pre-run spec confirmation** in Entries A/B (§4.2)
    is part of the `init` phase and is exempt; `--yes` removes even that.
  - *Code enforcement:* no blocking `input()` on the run path; any model output
    that ends in a question on the work path is treated as a **stall signal**.
- **B2 — Ready means execute.** If preparation is complete, the system MUST
  execute (submit/run/commit). It MUST NOT stop after preparing. (SKILL.md: the
  most common hidden violation is "finishing all prep then asking 'should I
  submit?'".)
- **B3 — Callback means report-alive.** The **first action** of every callback /
  iteration entrypoint MUST update its own `last_seen`, then check liveness,
  before doing anything else.
- **B4 — Persist state to files.** All progress MUST be written to `state/`
  files. Each iteration starts a **fresh session** injecting only curated state.
  **`resume` is forbidden** (SKILL.md: *"never use resume"*).
- **B5 — Guardian/worker separation.** A heartbeat patrol MAY take only three
  actions on tasks that are not its own: **liveness-check, restart, nudge.** It
  MUST NOT read their findings/data, modify their state, or alter their results.

> Note on numbering: the skill's *engineering* constraints are separate (see §12,
> EC1–EC6). The "escalate, never abandon silently" rule is **EC6**, not a B-rule.

> Any PR that weakens B1–B5 fails review.

**Required Tests (§3):** static/guardrail tests that fail the build if (a) any
`input()` or blocking prompt exists on the run path (B1); (b) any code path
passes `resume`/conversation history into a work agent (B4); (c) the watchdog
exposes any cross-task operation beyond check/restart/nudge (B5). See §8.4, §0.1.

---

## 4. CLI Specification (Claude Code / OpenCode-style)

### 4.1 Entry point
Console script: **`zhuri`** (also `python -m zhuri`).
Three task-input entries are provided; **REPL (Entry B) is the primary UX**.

### 4.2 Three ways to start a task

#### Entry A — One-shot ("prompt is the task")
```bash
zhuri "我想研究大模型 agent 强化学习，给我一份深度调研的综述"
```
Behavior:
1. Create a task workspace in CWD (`./.zhuri/tasks/<auto-id>/` by default; `--dir` to override).
2. Run a single **"spec synthesis"** LLM call (`spec` role, §4A) → structured
   `task_spec.md` (goal / milestones / success criteria).
3. **Print the synthesized spec for one confirmation** (default), then start the
   orchestrator + watchdog and run **unattended** (zero-interaction thereafter, B1).
4. `--yes` skips the confirmation and starts immediately.
5. `--detach` runs orchestrator/watchdog in the background and returns.

#### Entry B — Interactive REPL (PRIMARY, Claude Code/OpenCode-like)
```bash
zhuri
```
Opens a long-lived TTY. Behavior:
- A prompt box accepts the task in natural language.
- On submit: same **spec synthesis → confirm-once → launch** flow as Entry A.
- After launch, the REPL switches to a **live dashboard**: per-task status table,
  iteration counter, `stale_count`, latest findings, and a scrolling colored log
  tail (from `logs/*.jsonl`). Honors B1 (no further questions on the run path).
- REPL slash-commands (control, not Q&A; do not violate B1):
  `/status`, `/logs [work|orchestrator|heartbeat]`, `/pause`, `/resume`,
  `/pivot <task>` (force a structural pivot), `/stop`, `/spec` (show task_spec),
  `/new "<prompt>"` (add another concurrent task), `/config`, `/quit`.

#### Entry C — Config-file / scaffold (engineering & reproducible/CI)
```bash
zhuri init my-task --template paper-writing|blank
#   edit my-task/state/task_spec.md
zhuri run ./                       # orchestrate all tasks under a base dir
```
Suited to multi-task, reproducible, or service-style runs.

> All three entries converge on the same artifact: `state/task_spec.md` + the
> orchestrator. Only the *source of the task* differs.

### 4.3 Confirmation vs. Zero-Interaction (B1) boundary
The one-time pre-run spec confirmation (Entries A/B) is `init`-phase and exempt
from B1. **Once the run starts, B1 is absolute.** `--yes` removes even that.

### 4.4 Global UX
- Rich TTY output (`rich`): live status table, colored log tail.
- **Non-interactive by default** on the run path. Interactive prompts allowed
  ONLY in `init`/spec-confirmation and `config`.
- `--json` on read commands emits machine-readable output.
- Exit codes: `0` ok, `1` generic error, `2` config error, `3` provider/auth error.

### 4.5 Command summary

| Command | Purpose |
|---|---|
| `zhuri "<prompt>" [--dir D] [--yes] [--detach]` | **Entry A**: one-shot task from a prompt. |
| `zhuri` | **Entry B**: interactive REPL (primary). |
| `zhuri init <task-dir> [--template ...]` | **Entry C**: scaffold a task. |
| `zhuri run <base-dir> [--interval 2h] [--max-iters N] [--once]` | Start orchestrator loop. |
| `zhuri watchdog <base-dir> [--interval 1h]` | L1 durable patrol. |
| `zhuri guard <base-dir>` | L0 resident guard. |
| `zhuri work <task-dir> --direction "<d>" [--max-rounds 15] [--max-minutes 30]` | Single work-agent iteration (spawned as subprocess; also manual). |
| `zhuri status <base-dir> [--watch] [--json]` | Read-only status. |
| `zhuri logs <task-dir> [--source ...] [--level ...] [--follow]` | Read-only log tail. |
| `zhuri config [get\|set\|path\|check]` | Manage providers/agents/keys (§10A). |
| `zhuri doctor` | Validate env, provider auth, banned-deps check, cron/systemd. |

### 4.6 Time parsing
Accept `30m`, `2h`, `90s`, ISO durations. Centralize in `util/duration.py`.

**Required Tests (§4):** CLI dispatch table (each command routes correctly);
`--once` runs exactly one tick; `--yes` bypasses confirmation; exit codes per
failure class; duration parsing edge cases; REPL slash-command parsing. Entry
A/B/C end-to-end smoke tests (with fake provider) asserting all converge on a
valid `task_spec.md`.

---

## 4A. Task Spec Synthesis (prompt → task_spec.md)

`agents/spec_synthesis.py`:
- Input: raw user prompt (Entry A/B).
- One LLM call using the **`spec`** agent role (§10A); defaults to the
  `orchestrator` role if `spec` is unconfigured.
- Output: `state/task_spec.md` with at least **Goal**, **Milestones** (ordered),
  **Success criteria** (measurable), optional **Out-of-scope**, **Initial
  direction seed**.
- Shown for one confirmation unless `--yes`.
- Writes its own `last_seen` first (B3); logs at `level=decision`.

**Required Tests (§4A):** given a fixed prompt + fake provider, asserts a
well-formed `task_spec.md` with all mandatory fields; confirmation shown by
default and skipped with `--yes`; fallback to `orchestrator` role when `spec`
unset.

---

## 5. Repository / Module Layout

```
zhuri/
├── __main__.py                # python -m zhuri
├── cli.py                     # arg parsing + command dispatch (thin)
├── repl.py                    # Entry B interactive REPL + live dashboard
├── config.py                  # load/merge config, env interpolation, routing
├── orchestrator/
│   ├── loop.py                # monitor→detect→inject→launch cycle
│   ├── stall.py               # stall detection + pivot decision (§7)
│   └── diversity.py           # direction-diversity enforcement (§7.4)
├── agents/
│   ├── work_agent.py          # fresh-session work executor (§6)
│   ├── subagent.py            # A/B/C/D scheduling patterns (§9)
│   ├── spec_synthesis.py      # prompt → task_spec.md (§4A)
│   └── prompt.py              # prompt assembly (background+deliverable+caps)
├── watchdog/
│   ├── l0_guard.py            # resident, session-independent (§8.2)
│   ├── l1_patrol.py           # hourly durable patrol (§8.3)
│   └── liveness.py            # last_seen read/write + restart/nudge ops (§8.4)
├── state/
│   ├── store.py               # atomic read/write of state files (§6.4)
│   ├── models.py              # dataclasses: Progress, Finding, IterationLog...
│   └── locks.py               # cross-process file locking
├── providers/
│   ├── base.py                # LLMProvider ABC (§10)
│   ├── openai_compat.py       # OpenAI-compatible (Qwen/Kimi/DeepSeek/local)
│   └── registry.py            # role→provider/model routing + pool rotation
├── logging/
│   └── jsonl.py               # structured JSONL logger (§6.5)
├── tasks/                     # built-in task packs (skills)
│   └── paper_writing/
│       ├── pack.py            # phase routing, weakness routing
│       ├── subskills/         # literature, structure, experiment, figures, review
│       └── gates.py
└── util/
    ├── duration.py
    ├── proc.py                # safe subprocess spawn + timeout + capture
    └── ids.py
tests/
  ├── unit/
  ├── integration/            # real subprocess: work agent + watchdog
  └── guardrails/             # banned-deps, ≤300-line, no-interactive-on-run
SPEC.md
README.md
pyproject.toml                # console_scripts: zhuri
```

> **EC1 (SKILL.md §9):** no single source file > 300 lines; an iteration touches
> at most 5 large files. Split modules accordingly.

---

## 6. Work Agent (fresh session model)

### 6.1 Contract
`zhuri work <task-dir> --direction D` MUST:
1. **First line:** write `last_seen` for this work process (B3).
2. Load **curated** state: `task_spec.md`, `progress.json`, the tail of
   `directions_tried.json`, and a bounded slice of `findings.jsonl`. It MUST NOT
   load full conversation history (there is none — B4).
3. Construct the work prompt via `agents/prompt.py` (§6.3), using the **`work`**
   agent role for model routing (§10A).
4. Drive a bounded work loop: **cap 15 rounds OR 30 minutes**, whichever first
   (SKILL.md §6 round cap; configurable per call). Each round = one LLM call
   (+ optional tool/subagent).
5. **Run validation between iterations** (test/compile/check) and record it (EC3).
6. Append new findings to `findings.jsonl` (append-only), append a row to
   `iteration_log.jsonl`, and update `progress.json` **atomically**.
7. Exit. The process is **disposable**; nothing persists in memory.

### 6.2 Determinism of state writes
All writes go through `state/store.py` with file locks (`state/locks.py`) and
atomic temp-file-rename. Concurrent work agents on different tasks MUST be safe.

### 6.3 Prompt assembly (every subagent/work prompt MUST include)
Per SKILL.md §8: **background, a verifiable deliverable, working directory,
file/line caps, completion criteria.** `prompt.py` MUST refuse to build a prompt
missing any of these five fields.

### 6.4 State files (exact schema)
```
<task>/state/
├── task_spec.md            # goal / milestones / success criteria
├── progress.json           # see schema below
├── findings.jsonl          # append-only; one finding per line
├── directions_tried.json   # array of tried directions (diversity basis)
└── iteration_log.jsonl     # per-iteration summary, one per line
```
`progress.json`:
```json
{
  "task_id": "string",
  "iteration": 0,
  "status": "idle|running|stalled|pivoting|escalated|done",
  "total_findings": 0,
  "stale_count": 0,
  "last_metric": null,
  "last_seen": { "work": null, "orchestrator": null, "heartbeat": null },
  "updated_at": "ISO-8601"
}
```
`findings.jsonl` line:
```json
{"ts":"ISO-8601","iteration":3,"claim":"...","evidence":"...","verifiable":true,"source":"..."}
```
`directions_tried.json` element:
```json
{"iteration":3,"direction":"...","structural_axis":"...","result":"stall|gain","ts":"ISO-8601"}
```

### 6.5 Log files (exact schema)
```
<task>/logs/
├── work.jsonl              # work agent; decisions tagged level=decision
├── orchestrator.jsonl      # orchestrator
└── heartbeat.jsonl         # heartbeat watchdog
```
Every log line MUST be (SKILL.md §4 log format):
```json
{"ts":"ISO-8601","source":"work|orchestrator|heartbeat","level":"info|warn|error|decision","event":"...","detail":"..."}
```

**Required Tests (§6):**
- `last_seen` is written **before** any other side effect (B3) — assert ordering.
- Round/time cap enforced (stops at 15 rounds or 30 min; injectable clock).
- `findings.jsonl` append-only; `progress.json` updated atomically.
- Validation step (EC3) is invoked; an iteration without it is flagged failed.
- **Concurrency:** two work agents on two tasks write simultaneously with no
  corruption (real subprocess test + file locks).
- **No-resume guard (B4):** assert no conversation history is injected.

---

## 7. Orchestrator Loop & Stall Logic

### 7.1 Loop (`orchestrator/loop.py`)
The orchestrator may run as the **current session** or as a **durable cron**
(SKILL.md §3). On each tick (default 2h; `--once` = single tick; `--interval`
overrides):
1. **First action:** update orchestrator `last_seen` (B3).
2. For each task under `base-dir`:
   1. Read `progress.json`.
   2. If `stale_count >= 3`: generate a **fresh direction** (§7.4) before launching.
   3. Launch a work agent **as a subprocess** (`zhuri work ...`) with explicit
      `--direction`, max-rounds, max-minutes, completion criteria. **Zero
      interaction** (B1).
   4. On exit, read back state; recompute stall (§7.2).
3. Log decisions at `level=decision`.

### 7.2 Stall detection (`orchestrator/stall.py`)
- An iteration with **0 new findings** OR a **metric drop** ⇒ `stale_count += 1`.
- Otherwise reset `stale_count = 0` and update `last_metric`.

### 7.3 Forced pivot
- `stale_count >= 2` ⇒ **pivot structure, not tactics**: next direction MUST change
  a *structural constraint* (environment/framing/axis), logged with the axis changed.
- `stale_count >= 4` ⇒ `status="escalated"` and **flag for human attention** (§8.5).
  Per **EC6**, unresolved external-dependency failures escalate with a full report
  and a poll-for-reply, **never abandoned silently**.
- **Prepared-but-not-executed guard (B2):** if state shows prep complete but no
  execution recorded, inject an "execute now" direction instead of counting a stall.

### 7.4 Direction diversity (`orchestrator/diversity.py`)
- Before each iteration, read `directions_tried.json`.
- A new direction MUST differ from **every** tried direction (compare on a
  `structural_axis` key, not raw string).
- After a stall, inject a **perturbation strategy** (opposite hypothesis, or a
  structurally-similar-but-different framing).
- With multiple candidates, **prefer diversity over depth** (EC5).

**Required Tests (§7):**
- Stall table: 0 findings / metric drop ⇒ `stale_count+1`; gain ⇒ reset.
- Pivot at `stale_count>=2` changes `structural_axis` (not a tactical param) and
  logs a `level=decision` line; escalation at `>=4` sets `status=escalated`.
- Diversity rejects a candidate matching any tried `structural_axis`.
- B2 guard: prepared-but-not-executed yields an "execute" direction, not a stall.
- **Integration:** orchestrator + **mock** work agent run the full
  monitor→detect→inject→relaunch cycle through a forced pivot and an escalation.

---

## 8. Heartbeat Watchdog (3 layers)

> The business loop is itself unreliable; it needs an independent guardian layer.
> The three layers mutually check each other — any one dying can be detected and
> recovered by another (SKILL.md §7).

### 8.1 Layer table (MUST implement all three)
| Layer | Form | Depends on | Role |
|---|---|---|---|
| **L0** | resident shell-independent guard | **no session** | heartbeat timestamp stale **> 2h** ⇒ spin up an emergency patrol via a headless agent. |
| **L1** | durable scheduled job, **hourly** | a living scheduler (cron/systemd) | check each loop's `last_seen`; restart loops exceeded `interval × 3`; detect stalling and nudge. |
| **L2** | business loops (orchestrator + work) | each its own session | **first line** of each callback updates its own `last_seen`. |

### 8.2 L0 (`watchdog/l0_guard.py` + install recipe)
- Installable so it survives without any interactive session.
- v1 deliverable: (a) a tiny long-running guard watching only the heartbeat
  timestamp file and spawning the emergency patrol, AND (b) a documented `systemd`
  unit / shell-loop recipe in README for true session independence.
- L0 MUST NOT read task findings (B5).

### 8.3 L1 (`watchdog/l1_patrol.py`)
- Hourly. For each loop: `now - last_seen > interval × 3` ⇒ **restart**.
- For each task: no update for **> 2h AND last output is a question** ⇒ **stalled**
  ⇒ launch a **nudge subagent** (inject `task_spec` + `progress`, instruct it to
  resume execution).
- **Three consecutive nudges with no progress** ⇒ **stuck** ⇒ escalate
  (`status="escalated"`, surface to human) — SKILL.md §7. Zero interaction
  otherwise (B1).
- Installable as cron line or systemd timer (README recipes + `doctor` checks).

### 8.4 Liveness ops (`watchdog/liveness.py`) — the ONLY cross-task surface (B5)
Expose exactly three operations and nothing else:
- `check(task_or_loop) -> alive|stale`
- `restart(loop)`
- `nudge(task)`
No function here may read a task's findings or mutate its state beyond
restart/nudge bookkeeping.

### 8.5 Escalation surfacing
Escalations (§7.3) are written to `<task>/state/progress.json:status` and
`<base>/escalations.jsonl`. `status` highlights them. Per **EC6** the escalation
record MUST be a full report and MUST poll for a reply hook (config).

**Required Tests (§8):**
- L2: every callback writes `last_seen` first (B3).
- L1: stale `last_seen > interval×3` ⇒ restart (real subprocess); task with no
  update >2h ending in a question ⇒ nudge; **3 nudges, no progress ⇒ escalate**.
- L0: stale heartbeat >2h ⇒ spawns emergency patrol (injectable clock).
- **B5 surface test:** `liveness` module exposes ONLY check/restart/nudge; a
  guardrail test fails if any findings-read/state-mutate function is added.

---

## 9. Subagent Scheduling Patterns (A/B/C/D)

Implement in `agents/subagent.py`. Each pattern builds prompts via `prompt.py`
(§6.3), runs as an isolated process/call, and routes its model via the
`subagent.<name>` agent role (inherits from parent role if unset — §10A).

| Pattern | Use | Key behavior |
|---|---|---|
| **A — Goal-driven** | research iteration | Inject tried directions; require **verifiable** findings; write back to `findings.jsonl`. |
| **B — Parallel exploration** | complex sub-problems | Fire **multiple** subagents in one batch (investigation, refutation, cross-domain analogy); gather + reconcile. |
| **C — Experiment run** | long compute jobs | Start **minute-level polling right after submit**; auto-diagnose errors, fix, resubmit. |
| **D — Verification** | post-iteration QA | An **independent** subagent audits the evidence chain of findings. |

Pattern B MUST support true concurrency (`asyncio.gather` over subprocesses /
async provider calls).

**Required Tests (§9):**
- A writes verifiable findings back; D runs as an **independent** call (different
  context) and can flag an unsupported finding.
- B launches N subagents **concurrently** (assert overlap, not serial) and
  reconciles results.
- C begins polling immediately after a (faked) submit and auto-retries on a
  simulated error.
- Sub-role model routing falls back to parent role when unset.

---

## 10. LLM Provider Layer (framework-free)

### 10.1 Two-tier configuration model
1. **`[providers.*]`** — *what model endpoints exist*, each with its own key.
2. **`[agents.*]`** — *which provider/model each agent role uses* (how
   "different agent → different key/model" is achieved).

Resolution order for any role's effective (provider, model, key):
`[agents.<role>]` → `[agents.default]` → error if neither resolves.
Sub-roles (e.g. `[agents.subagent.verification]`) **inherit from their parent
role** when unset (optional override, inherit upward by default).

### 10.2 v1 built-in providers
v1 ships **exactly one provider type**: `openai_compat` (OpenAI-compatible Chat
Completions). This single type covers **Qwen, Kimi (Moonshot), DeepSeek** via
different `base_url`/`api_key`/`models`.
- OpenAI, Anthropic, local vLLM/Ollama as first-class presets are **deferred to a
  later version** (the `openai_compat` type can already reach any local
  OpenAI-compatible server via a custom `base_url`).
- `providers/base.py` `LLMProvider` ABC is called **directly** — no agent
  framework may wrap it (A9, enforced by `doctor` + guardrail test).

### 10.3 `providers/base.py`
```python
class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, *, system: str, messages: list[dict],
                       model: str, max_tokens: int, temperature: float,
                       tools: list | None = None) -> ProviderResult: ...
```
MUST support: streaming (for TTY), optional tool/function calling, per-call model
selection (routing in `registry.py`). Auth failure ⇒ exit code 3 with an
actionable message.

### 10.4 Provider presets (developer convenience)
Ship known `base_url` presets so users only supply a key:
| Preset | base_url | Auth env (default) |
|---|---|---|
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| `qwen` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `QWEN_API_KEY` |
| `kimi` | `https://api.moonshot.cn/v1` | `MOONSHOT_API_KEY` |
Users may define arbitrary `[providers.<name>]` with a custom `base_url`.

### 10.5 Per-round model diversity
An agent role MAY define a **model pool** (`models = [...]`). The registry MUST be
able to force a **different model for at least one agent per round** (peer-review
anti-inflation, direction diversity). Pool rotation is deterministic per round
(seedable for reproducibility).

**Required Tests (§10):**
- `complete()` contract honored by a **fake** provider (streaming + non-stream).
- Auth failure ⇒ exit code 3.
- Pool rotation is deterministic under a fixed seed and yields a different model
  for the designated agent each round.
- Guardrail: provider is invoked directly (no agent-framework import on the path).

---

## 10A. Configuration Schema

### 10A.1 Location & precedence
- File: `~/.config/zhuri/config.toml`, overridable by `--config PATH` or
  `ZHURI_CONFIG` env.
- A per-project `./.zhuri/config.toml` (if present) **overrides** the user file.
- Env-var interpolation: any string value may use `${ENV_VAR}`; missing required
  vars cause a clear error (exit 3) via `zhuri config check` and `doctor`.

### 10A.2 `[providers.*]`
```toml
[providers.deepseek]
type     = "openai_compat"
base_url = "https://api.deepseek.com/v1"   # optional if preset name == provider name
api_key  = "${DEEPSEEK_API_KEY}"
models   = ["deepseek-chat", "deepseek-reasoner"]

[providers.qwen]
type     = "openai_compat"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key  = "${QWEN_API_KEY}"
models   = ["qwen-max", "qwen-plus"]

[providers.kimi]
type     = "openai_compat"
base_url = "https://api.moonshot.cn/v1"
api_key  = "${MOONSHOT_API_KEY}"
models   = ["kimi-k2-0905-preview", "moonshot-v1-128k"]
```

### 10A.3 `[agents.*]` (role → provider/model; per-agent key follows provider)
```toml
[agents.default]                 # fallback for any unset role
provider = "deepseek"
model    = "deepseek-chat"

[agents.orchestrator]            # stable & cheap
provider = "deepseek"
model    = "deepseek-chat"

[agents.spec]                    # prompt → task_spec synthesis (§4A)
provider = "deepseek"
model    = "deepseek-reasoner"

[agents.work]                    # strongest model for doing the work
provider = "qwen"
model    = "qwen-max"

[agents.review]                  # different vendor on purpose; may use a pool
provider = "kimi"
models   = ["kimi-k2-0905-preview", "moonshot-v1-128k"]

# Optional sub-role overrides; inherit from parent role if omitted
[agents.subagent.verification]
provider = "deepseek"
model    = "deepseek-reasoner"
# [agents.subagent.nudge]  # unset → inherits from [agents.work] / [agents.default]
```

### 10A.4 Validation rules
- `zhuri config check` MUST verify: every `[agents.*]` references an existing
  `[providers.*]`; every referenced model is listed under that provider's
  `models`; every required `api_key` env resolves; no banned agent-framework deps.
- A role with both `model` and `models` is invalid (pick one).
- `doctor` runs `config check` plus a **live 1-token auth probe** per distinct key
  (skippable with `--offline`).

### 10A.5 Effective-config introspection
`zhuri config get --effective [--role work] [--json]` prints the fully-resolved
(provider, model, base_url, key-source) per agent role, with keys **masked**.

**Required Tests (§10A):**
- Resolution + inheritance: unset sub-role inherits parent; `agents.default`
  fallback works; dangling agent→provider ref fails `config check`.
- Unlisted model under a provider fails; both-`model`-and-`models` fails.
- Env interpolation resolves `${VAR}`; missing var ⇒ exit 3.
- `get --effective` masks secrets (no raw key in output).

---

## 11. Reference Task Pack — Scientific Paper Writing skill group

> Source: https://victorchen96.github.io/auto_research/skill/paper-writing.html
> Implement under `tasks/paper_writing/`. Validates the orchestrator against a
> real, hierarchical multi-agent workload.

### 11.1 Five sub-skills (each a subagent role)
1. **Literature Survey** — Recall → LQS score → Classify A/B/C/D → Venue upgrade.
   IN: topic+taxonomy keywords. OUT: `references.bib` + `citation_plan.jsonl`.
   Verify every 20 citations; hallucinated = 0 (EC4).
2. **Paper Structure & Logic** — chapter architecture, paragraph logic patterns,
   MECE taxonomy, hedged formal claims. OUT: `sections/*.tex` (≤300 lines each).
3. **Experiment Design** — Design→Execute(API/GPU)→Iterate(≤5)→Report. OUT:
   `results.json` + `experiment_summary.md` (data only; no LaTeX figures here).
4. **Academic Figures & Tables** — booktabs tables + vector figures from
   `results.json`. OUT: `figures/*.pdf` + `tables/*.tex`.
5. **Peer Review Simulation** — 3–5 reviewer personas, independent scoring,
   **median** final score, anti-inflation rules; **drives the iteration loop** by
   routing weaknesses back to sub-skills #1–4.

### 11.2 Phase routing (orchestrator directions)
- **Phase 0** Topic selection (Scope/Angle/Audience) — pre-pipeline.
- **Phase 1** Draft, iters 1–6, target 6.0.
- **Phase 2** Deep improvement, iters 7–9, target 7.5–8.0.
- **Phase 3** Sprint, iters 10+, target 8.5+. **Stop when** score ≥ 8.5 OR Δ ≤ 0.3
  for 2 rounds OR iter > 12.

### 11.3 Weakness-routing table (`tasks/paper_writing/pack.py`)
Implement the full mapping reviewer-weakness → responsible sub-skill → action
(e.g. "Too many arXiv-only refs" → Literature → Stage-4 upgrade; "No experiments"
→ Experiment → design pilot; "No error bars" → Figures → add ±std). The table
MUST be data-driven (dict/JSON), not hardcoded branches.

### 11.4 Quality gates (`tasks/paper_writing/gates.py`)
Five gates; Gates 1&2 may run in parallel; **Gate 5 is blocking**:
Gate 1 Literature, Gate 2 Experiment, Gate 3 Structure, Gate 4 Figures&Tables,
Gate 5 Final Review (all 1–4 passed, PDF compiles clean, score ≥ phase target, no
regression, version bumped + snapshot saved). Each gate is a pure function
`gate(state) -> (passed: bool, reasons: list[str])`.

### 11.5 Anti-inflation (review loop)
First-round score capped at 7.0; max +1.5 per round; ≥1 unresolved weakness must
remain; ≥1 reviewer per round MUST use a different model (ties to §10.5).

**Required Tests (§11):**
- Each gate function is pure and returns precise failure reasons; Gate 5 blocks
  when any of 1–4 fails or score < phase target or a regression is detected.
- Weakness-routing table maps every documented weakness to the correct sub-skill
  (data-driven; table-coverage test).
- Anti-inflation: first round capped at 7.0; max +1.5/round; ≥1 unresolved
  weakness remains; ≥1 reviewer uses a different model.
- Phase routing stop-conditions (≥8.5 OR Δ≤0.3×2 OR iter>12) trigger correctly.

---

## 12. Engineering Constraints (MUST, from SKILL.md §9)

- **EC1** ≤ 5 large files per iteration; **no file > 300 lines** (applies to BOTH
  generated artifacts AND this project's own source).
- **EC2** State is injected via files, never conversation history.
- **EC3** Validation (test/compile/check) MUST run between iterations.
- **EC4** Citation-like content verified **every 20 entries**, never batched up.
- **EC5** With multiple candidate directions, prefer diversity over depth.
- **EC6** Unresolvable external-dependency failures escalate (full report +
  notify owner + poll for reply); never abandon silently.

**Required Tests (§12):** guardrail test enforcing EC1 (≤300 lines/file) across
the whole source tree; a test asserting EC4 cadence (verification fires every 20
entries) in the literature sub-skill; EC3 wired into the work-agent loop (§6).

---

## 13. Open Questions (resolve before coding affected module)

1. **L0 install target**: `systemd`, a bare shell `while` loop, or both?
   (Affects `watchdog/l0_guard.py` + README.)
2. **Tooling for work agents**: what tool surface (shell exec? file IO? web
   search?) is exposed to a work agent, and how is it sandboxed?
3. **"Last output is a question" detection** (§8.3): heuristic (regex on trailing
   `?`) vs. a classifier call — pick one and document false-positive handling.
4. **Escalation reply hook** (§8.5/EC6): channel for "poll for a reply"
   (file flag? webhook? email?).
5. **REPL concurrency model**: does the REPL host the orchestrator in-process
   (asyncio task) or spawn it as a child process it monitors? (Affects `repl.py`.)

> Resolved earlier in design discussion: provider default & routing (§10/§10A);
> task-input UX (§4, three entries, REPL primary); name (`zhuri`).

---

## 14. Acceptance Criteria (Definition of Done for v1)

A1. `zhuri` exposes all commands in §4.5; `--once` performs exactly one
    orchestrator tick.
A2. **Three task-input entries** work: one-shot (A), REPL (B, primary, with live
    dashboard + slash-commands), config-file (C). All converge on `task_spec.md`.
A3. Prompt→spec synthesis (§4A) produces a structured `task_spec.md`; a **single
    pre-run confirmation** is shown by default and skipped with `--yes`.
A4. A work agent runs as a **separate process**, writes `last_seen` first (B3),
    respects the **15-round / 30-min** cap, runs validation (EC3), and persists
    findings atomically. **No `resume` code path exists** (B4).
A5. Stall → `stale_count`; `>=2` forces a **structural** pivot (logged with axis);
    `>=4` escalates. Diversity enforced on a `structural_axis` key.
A6. All three watchdog layers exist; L1 restarts loops past `interval×3` and
    nudges tasks stalled >2h on a trailing question; 3 failed nudges escalate.
    The watchdog's only cross-task surface is `check/restart/nudge` (B5).
A7. Subagent patterns A/B/C/D implemented; B runs subagents concurrently;
    sub-roles route via `[agents.subagent.*]` and inherit when unset.
A8. **Two-tier config** works: `[providers.*]` + `[agents.*]`, env interpolation,
    **per-role provider/model/key routing**, `qwen`/`kimi`/`deepseek` presets,
    `config check` + `config get --effective` (masked). v1 ships only
    `openai_compat`.
A9. NO dependency on crewai/langgraph/langchain-agents/autogen/llama-index in
    `pyproject.toml`; provider layer is called directly. `doctor` asserts this.
A10. Paper-writing pack: 5 sub-skills, phase routing, data-driven weakness
    routing, 5 gates (Gate 5 blocking), anti-inflation — all unit-tested.
A11. Every source file ≤ 300 lines (EC1). CI check enforces it.
A12. Zero `input()` / interactive blocking on the run path (B1); the only
    interactive points are spec-confirmation and `config`. CI grep enforces.
A13. README documents the Claude Code/OpenCode-style UX (three entries),
    the two-tier config, the file-based message bus, and L0/L1 install recipes.
A14. **Testing Discipline (§0.1) satisfied:** every functional unit has its
    `Required Tests`; coverage ≥85% overall and ≥90% in core; all milestone test
    gates (§16) green; no real-LLM calls in tests (fake provider only).

---

## 15. Test Plan (high level)

> This complements — does not replace — the per-section `Required Tests` and the
> Testing Discipline (§0.1). The agent MUST implement both.

- **Unit:** `state/store.py` atomic+locked writes under concurrency;
  `stall.py`/`diversity.py` decision tables; each gate function; weakness-routing
  coverage; `duration.py`; `config.py` resolution + inheritance + env interpolation.
- **Process/integration:** orchestrator spawns a **mock** work agent (stub
  `zhuri work` writing deterministic findings) and verifies the full
  monitor→detect→inject→relaunch cycle, including forced pivot at `stale>=2` and
  escalation at `stale>=4`; **real subprocess** spawning for work agents and the
  watchdog.
- **Watchdog:** simulate stale `last_seen` → L1 restart; trailing-question stall →
  nudge; 3-nudge → escalate; stale heartbeat >2h → L0 emergency patrol.
- **Entries:** A writes a spec + launches; B (REPL) submits a prompt, confirms,
  shows dashboard; C scaffolds + runs. `--yes` bypasses confirmation.
- **Config:** `config check` catches dangling agent→provider refs, unlisted
  models, missing env keys; `get --effective` masks secrets.
- **Guardrails:** static checks for A9/A11/A12 (no banned deps, ≤300 lines, no
  interactive blocking on the run path).
- **Provider:** contract tests against a fake `openai_compat` provider
  (streaming + non-streaming + auth failure + pool rotation).

---

## 16. Milestones (each ends with an EXIT TEST GATE — do not proceed until green)

1. **Foundations** — `state/` + `logging/` + `config/` (two-tier + presets +
   interpolation) + `util/`.
   *Gate:* unit tests for state atomicity/locking, config resolution/inheritance,
   duration parsing; coverage floor for `state/` & `config.py` met.
2. **Provider + prompt + work agent** — `providers/` (`base` + `openai_compat` +
   `registry`) + `agents/prompt.py` + `agents/spec_synthesis.py` +
   `agents/work_agent.py`.
   *Gate:* fake-provider contract tests; prompt-completeness rejection test;
   work-agent `last_seen`-first + round/time cap + atomic findings (real
   subprocess); spec-synthesis output well-formed.
3. **Orchestrator** — `orchestrator/` (loop + stall + diversity).
   *Gate:* stall/pivot/diversity unit tests **plus** the orchestrator+mock-work
   integration cycle (pivot at ≥2, escalate at ≥4) green.
4. **Watchdog** — L2 → L1 → L0 + `doctor` checks.
   *Gate:* restart/nudge/escalate integration tests; B5 surface guardrail; L0
   emergency-patrol test.
5. **Subagents** — `agents/subagent.py` patterns A/B/C/D.
   *Gate:* concurrency test for B; independence test for D; A write-back; C
   polling/retry; sub-role routing/inheritance.
6. **CLI + REPL** — `cli.py` + `repl.py` (three entries; dashboard + slash-cmds).
   *Gate:* Entry A/B/C smoke tests; `--yes` bypass; slash-command parsing; exit
   codes; B1 guardrail (no interactive blocking on run path).
7. **Paper-writing pack** — `tasks/paper_writing/` + gates + routing.
   *Gate:* gate purity + Gate-5 blocking; routing-table coverage; anti-inflation;
   phase stop-conditions.
8. **Hardening & docs** — packaging, README, CI guardrails, coverage floors.
   *Gate:* full suite green; coverage ≥85% overall / ≥90% core; all §14 met,
   especially **A14**.