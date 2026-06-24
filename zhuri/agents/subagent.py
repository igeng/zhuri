"""Subagent scheduling patterns A/B/C/D (§9).

Each pattern builds prompts via :mod:`zhuri.agents.prompt`, runs as an isolated
call, and routes its model via the ``subagent.<name>`` role (inheriting from the
parent role when unset). Pattern B supports true concurrency via ``asyncio.gather``.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from ..providers.registry import Registry
from ..state.models import Finding
from ..state.store import TaskStore
from .prompt import build_prompt


@dataclass
class SubagentReport:
    name: str
    text: str
    model: str
    findings: list[Finding] = field(default_factory=list)


def _parse_findings(text: str, iteration: int) -> list[Finding]:
    from .work_agent import extract_findings

    return extract_findings(text, iteration)


async def _call(registry: Registry, role: str, *, deliverable: str, working_dir: str,
                background: str, completion: str) -> tuple[str, str]:
    provider, eff = registry.provider_for(role)
    prompt = build_prompt(
        background=background,
        deliverable=deliverable,
        working_dir=working_dir,
        caps="files <= 300 lines",
        completion_criteria=completion,
    )
    result = await provider.complete(
        system=prompt.system,
        messages=[{"role": "user", "content": prompt.user}],
        model=eff.model,
    )
    return result.text, eff.model


# -- Pattern A: goal-driven research --------------------------------------
async def pattern_a_async(task_dir, registry: Registry, *, goal: str) -> SubagentReport:
    """Inject tried directions, require verifiable findings, write them back."""
    store = TaskStore(task_dir)
    store.ensure_dirs()
    iteration = (store.read_progress().iteration if store.read_progress() else 0) + 1
    text, model = await _call(
        registry, "subagent.research",
        background=store.read_task_spec() or goal,
        deliverable=f"Verifiable findings for: {goal}",
        working_dir=str(store.task_dir),
        completion="Emit 'FINDING: <claim> :: <evidence>' lines.",
    )
    findings = _parse_findings(text, iteration)
    for f in findings:
        store.append_finding(f)
    return SubagentReport("research", text, model, findings)


# -- Pattern B: parallel exploration --------------------------------------
async def pattern_b_async(task_dir, registry: Registry, *, subproblems: list[str]
                          ) -> list[SubagentReport]:
    """Fire multiple subagents concurrently, then gather + reconcile."""
    store = TaskStore(task_dir)
    store.ensure_dirs()

    async def one(sp: str) -> SubagentReport:
        text, model = await _call(
            registry, "subagent.explore",
            background=store.read_task_spec() or sp,
            deliverable=f"Investigate sub-problem: {sp}",
            working_dir=str(store.task_dir),
            completion="Report findings or a refutation.",
        )
        return SubagentReport(sp, text, model, _parse_findings(text, 0))

    reports = await asyncio.gather(*(one(sp) for sp in subproblems))
    return list(reports)


def reconcile(reports: list[SubagentReport]) -> list[Finding]:
    """Merge findings from parallel subagents, de-duplicating on claim."""
    seen: dict[str, Finding] = {}
    for rep in reports:
        for f in rep.findings:
            seen.setdefault(f.claim, f)
    return list(seen.values())


# -- Pattern C: experiment run --------------------------------------------
@dataclass
class ExperimentResult:
    submits: int
    polls: int
    succeeded: bool
    last_status: str


async def pattern_c_async(
    *, submit, poll, fix, max_submits: int = 3, poll_interval: float = 0.0,
    sleep=asyncio.sleep,
) -> ExperimentResult:
    """Start minute-level polling right after submit; auto-fix and resubmit.

    ``submit``/``poll``/``fix`` are injected coroutines: ``poll`` returns one of
    ``running|done|error``.
    """
    submits = 0
    polls = 0
    handle = await submit()
    submits += 1
    while True:
        status = await poll(handle)
        polls += 1
        if status == "done":
            return ExperimentResult(submits, polls, True, status)
        if status == "error":
            if submits >= max_submits:
                return ExperimentResult(submits, polls, False, status)
            await fix(handle)
            handle = await submit()
            submits += 1
            continue
        await sleep(poll_interval)  # status == running: keep polling


# -- Pattern D: independent verification ----------------------------------
async def pattern_d_async(task_dir, registry: Registry, findings: list[Finding]
                          ) -> dict:
    """Independent audit of the evidence chain; flags unsupported findings."""
    store = TaskStore(task_dir)
    listing = "\n".join(f"- {f.claim} :: {f.evidence}" for f in findings)
    text, model = await _call(
        registry, "subagent.verification",
        background="Audit the following findings independently:\n" + listing,
        deliverable="Flag any finding lacking verifiable evidence.",
        working_dir=str(store.task_dir),
        completion="Emit 'FLAG: <claim>' for each unsupported finding.",
    )
    flagged = [
        line[len("FLAG:"):].strip()
        for line in text.splitlines()
        if line.strip().upper().startswith("FLAG:")
    ]
    return {"model": model, "flagged": flagged, "text": text}


# -- sync wrappers ---------------------------------------------------------
def pattern_a(task_dir, registry, *, goal):
    return asyncio.run(pattern_a_async(task_dir, registry, goal=goal))


def pattern_b(task_dir, registry, *, subproblems):
    return asyncio.run(pattern_b_async(task_dir, registry, subproblems=subproblems))


def pattern_d(task_dir, registry, findings):
    return asyncio.run(pattern_d_async(task_dir, registry, findings))
