"""Task spec synthesis: prompt → task_spec.md (§4A).

One LLM call using the ``spec`` role (falls back to ``orchestrator`` when ``spec``
is unconfigured). Writes its own ``last_seen`` first (B3) and logs at
``level=decision``. Produces a structured ``state/task_spec.md`` with Goal,
Milestones, Success criteria, Out-of-scope, and an Initial direction seed.
"""
from __future__ import annotations

import asyncio

from ..logging.jsonl import JsonlLogger
from ..providers.registry import Registry
from ..state.store import TaskStore

MANDATORY_HEADINGS = ("# Goal", "## Milestones", "## Success criteria")

_SYSTEM = (
    "You are a research planning agent. Convert the user's request into a concise, "
    "structured task specification in Markdown. You MUST include the headings: "
    "'# Goal', '## Milestones' (ordered list), '## Success criteria' (measurable). "
    "Also include '## Out-of-scope' and '## Initial direction seed'. Do not ask "
    "questions; resolve ambiguity yourself."
)


def _fallback_spec(prompt: str) -> str:
    return (
        f"# Goal\n{prompt.strip()}\n\n"
        "## Milestones\n1. Scope and frame the problem.\n"
        "2. Gather evidence / build the core artifact.\n"
        "3. Validate and refine until success criteria are met.\n\n"
        "## Success criteria\n- A verifiable deliverable addressing the goal.\n"
        "- Independent validation passes.\n\n"
        "## Out-of-scope\n- Anything not required to satisfy the goal.\n\n"
        "## Initial direction seed\nStart by decomposing the goal into measurable sub-questions.\n"
    )


def _ensure_headings(text: str, prompt: str) -> str:
    if all(h in text for h in MANDATORY_HEADINGS):
        return text
    return _fallback_spec(prompt)


def pick_spec_role(registry: Registry) -> str:
    cfg = registry.config
    if cfg.has_explicit_role("spec"):
        return "spec"
    # §4A: defaults to the ``orchestrator`` role when ``spec`` is unconfigured.
    return "orchestrator"


async def synthesize_spec_async(
    task_dir, prompt: str, registry: Registry
) -> str:
    store = TaskStore(task_dir)
    store.ensure_dirs()
    # B3: write last_seen first.
    store.touch_last_seen("orchestrator")
    logger = JsonlLogger(store.logs_dir, "orchestrator")
    logger.decision("spec_synthesis_start", detail=prompt[:160])

    role = pick_spec_role(registry)
    provider, eff = registry.provider_for(role)
    logger.info("llm_request", detail=f"role={role} provider={eff.provider} model={eff.model}")
    result = await provider.complete(
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        model=eff.model,
        max_tokens=1024,
        temperature=0.3,
    )
    logger.info("llm_response", detail=f"chars={len(result.text)}")
    spec_md = _ensure_headings(result.text, prompt)
    store.write_task_spec(spec_md)
    # Initialize progress for the task.
    prog = store.read_progress()
    if prog is None:
        from ..state.models import Progress

        store.write_progress(Progress.new(store.task_dir.name))
    logger.decision("spec_synthesis_done", detail=f"role={role} model={eff.model}")
    return spec_md


def synthesize_spec(task_dir, prompt: str, registry: Registry) -> str:
    """Synchronous wrapper around :func:`synthesize_spec_async`."""
    return asyncio.run(synthesize_spec_async(task_dir, prompt, registry))
