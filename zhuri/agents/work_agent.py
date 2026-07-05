"""Work agent: fresh-session bounded executor (§6).

Contract (§6.1):
1. write ``last_seen`` first (B3);
2. load **curated** state only (no conversation history — B4);
3. build the prompt via :mod:`zhuri.agents.prompt`;
4. drive a bounded loop (cap 15 rounds OR 30 minutes);
5. run validation between iterations (EC3);
6. append findings + an iteration_log row + update progress atomically;
7. exit (the process is disposable).
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Callable

from ..logging.jsonl import JsonlLogger
from ..providers.registry import Registry
from ..state.models import Finding, IterationLog
from ..state.store import TaskStore
from .prompt import build_prompt

Clock = Callable[[], float]
Validator = Callable[["TaskStore"], bool]


@dataclass
class WorkResult:
    iteration: int
    new_findings: int
    rounds: int
    validated: bool
    stalled_on_question: bool
    stopped_reason: str


def _default_validator(store: TaskStore) -> bool:
    """Default EC3 validation: state files are well-formed and present."""
    return store.read_progress() is not None


def extract_findings(text: str, iteration: int) -> list[Finding]:
    """Parse ``FINDING: <claim> :: <evidence>`` lines from a model response."""
    findings: list[Finding] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.upper().startswith("FINDING:"):
            continue
        body = line[len("FINDING:"):].strip()
        claim, _, evidence = body.partition("::")
        findings.append(
            Finding(
                claim=claim.strip(),
                evidence=evidence.strip() or claim.strip(),
                iteration=iteration,
                verifiable=bool(evidence.strip()),
            )
        )
    return findings


async def run_work_async(
    task_dir,
    direction: str,
    registry: Registry,
    *,
    max_rounds: int = 15,
    max_minutes: float = 30.0,
    clock: Clock = time.monotonic,
    validator: Validator | None = None,
) -> WorkResult:
    store = TaskStore(task_dir)
    store.ensure_dirs()
    # (1) B3: report-alive first, before any other side effect.
    progress = store.touch_last_seen("work")
    logger = JsonlLogger(store.logs_dir, "work")
    logger.info("work_start", detail=f"direction={direction!r}")

    iteration = progress.iteration + 1

    # (2) curated state only — explicitly NO conversation history (B4).
    spec = store.read_task_spec() or "(no task_spec)"
    tried = [d.direction for d in store.read_directions()]
    # §6.1: inject a bounded slice of prior findings (never the full history).
    recent_findings = store.read_findings(tail=20)
    findings_block = (
        "# Prior findings (most recent, curated)\n"
        + "\n".join(f"- {f.claim} :: {f.evidence}" for f in recent_findings)
        if recent_findings
        else ""
    )

    # (3) assemble prompt (must contain all five mandatory fields).
    prompt = build_prompt(
        background=spec[:2000],
        deliverable=f"Make verifiable progress on: {direction}",
        working_dir=str(store.task_dir),
        caps=f"<= {max_rounds} rounds, <= {max_minutes} minutes, files <= 300 lines",
        completion_criteria="Emit 'FINDING: <claim> :: <evidence>' lines; say DONE when complete.",
        directions_tried=tried,
        extra=findings_block,
    )

    provider, eff = registry.provider_for("work")
    logger.info("work_config", detail=f"provider={eff.provider} model={eff.model}")
    start = clock()
    deadline = start + max_minutes * 60.0
    rounds = 0
    new_findings = 0
    stalled = False
    stopped = "max_rounds"
    messages = [{"role": "user", "content": prompt.user}]

    while rounds < max_rounds and clock() < deadline:
        rounds += 1
        model = registry.model_for_round("work", rounds)
        round_start = clock()
        logger.info("llm_request", detail=f"round={rounds} model={model}")
        result = await provider.complete(
            system=prompt.system,
            messages=messages,
            model=model,
            max_tokens=1024,
        )
        elapsed = round((clock() - round_start) * 1000)
        logger.info("llm_response",
                     detail=f"round={rounds} chars={len(result.text)}",
                     duration_ms=elapsed)
        print(f"  [work] round {rounds}/{max_rounds}  {len(result.text)} chars  "
              f"{elapsed}ms  findings_this_round={len(extract_findings(result.text, iteration))}",
              flush=True)
        # B1: a work-path answer ending on a question is a stall signal.
        if result.ends_with_question():
            stalled = True
            stopped = "question_stall"
            logger.decision("question_stall", detail="model ended on a question")
            print("  [work] ⚠ stall signal — model ended on a question", flush=True)
            break
        for finding in extract_findings(result.text, iteration):
            store.append_finding(finding)
            new_findings += 1
        if "DONE" in result.text:
            stopped = "done"
            break

    # (5) EC3 validation between iterations.
    validate = validator or _default_validator
    validated = bool(validate(store))
    logger.decision("validation", detail=f"validated={validated}")

    result_label = "gain" if new_findings > 0 else "stall"
    store.append_iteration_log(
        IterationLog(
            iteration=iteration,
            direction=direction,
            new_findings=new_findings,
            metric=float(new_findings),
            validated=validated,
            result=result_label,
        )
    )
    total = store.read_progress().total_findings + new_findings
    store.update_progress(
        iteration=iteration,
        total_findings=total,
        status="running",
    )
    logger.info("work_done", detail=f"rounds={rounds} findings={new_findings}")
    return WorkResult(
        iteration=iteration,
        new_findings=new_findings,
        rounds=rounds,
        validated=validated,
        stalled_on_question=stalled,
        stopped_reason=stopped,
    )


def run_work(task_dir, direction, registry, **kwargs) -> WorkResult:
    """Synchronous wrapper around :func:`run_work_async`."""
    return asyncio.run(run_work_async(task_dir, direction, registry, **kwargs))
