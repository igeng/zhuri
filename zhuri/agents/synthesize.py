"""Direct synthesis agent: consolidate findings into a final document.

When invoked, reads all accumulated findings from ``findings.jsonl`` and the
task spec, then makes a single LLM call to produce a comprehensive final
deliverable (e.g. a research survey, report, etc.). This bypasses the
multi-iteration loop for users who want a one-shot result.

The synthesized document is written to ``state/deliverable.md`` and the task
status is set to ``done``.
"""
from __future__ import annotations

import asyncio

from ..logging.jsonl import JsonlLogger
from ..providers.registry import Registry
from ..state.store import TaskStore

_SYSTEM = (
    "You are a synthesis agent. Your job is to consolidate research findings "
    "into a comprehensive, well-structured final document. Organize the "
    "material logically with clear sections, provide analysis and connections "
    "between findings, and produce a polished deliverable. Write in the "
    "language that matches the user's original goal description. Do NOT ask "
    "questions; produce the complete document directly."
)


def _build_synthesis_prompt(spec: str, findings_text: str) -> str:
    return (
        "# Task Specification\n"
        f"{spec}\n\n"
        "# Accumulated Research Findings\n"
        f"{findings_text}\n\n"
        "# Instructions\n"
        "Based on the task specification and all findings above, produce a "
        "comprehensive, well-structured final document that fully addresses "
        "the goal. Include an executive summary, organized sections covering "
        "all key themes, analysis of connections and trends, and a conclusion. "
        "Output the complete document in Markdown format."
    )


async def synthesize_document_async(
    task_dir,
    registry: Registry,
    *,
    max_tokens: int = 4096,
) -> str:
    """Read findings + spec, produce a final deliverable document."""
    store = TaskStore(task_dir)
    store.ensure_dirs()
    # B3: report alive first.
    store.touch_last_seen("work")
    logger = JsonlLogger(store.logs_dir, "work")
    logger.decision("synthesis_start", detail="direct synthesis mode")

    spec = store.read_task_spec() or "(no task specification)"
    findings = store.read_findings()

    if not findings:
        logger.info("synthesis_skip", detail="no findings to synthesize")
        return ""

    findings_text = "\n".join(
        f"- [{f.iteration}] {f.claim} :: {f.evidence}" for f in findings
    )

    prompt = _build_synthesis_prompt(spec, findings_text)
    provider, eff = registry.provider_for("work")
    logger.info("llm_request", detail=f"provider={eff.provider} model={eff.model} findings={len(findings)} spec_len={len(spec)}")
    result = await provider.complete(
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        model=eff.model,
        max_tokens=max_tokens,
        temperature=0.3,
    )
    logger.info("llm_response", detail=f"chars={len(result.text)}")

    # Write the deliverable.
    deliverable_path = store.state_dir / "deliverable.md"
    deliverable_path.write_text(result.text, encoding="utf-8")

    # Mark task as done.
    store.update_progress(status="done")
    logger.decision("synthesis_done", detail=f"len={len(result.text)}")
    return result.text


def synthesize_document(task_dir, registry: Registry, **kwargs) -> str:
    """Synchronous wrapper around :func:`synthesize_document_async`."""
    return asyncio.run(synthesize_document_async(task_dir, registry, **kwargs))


async def _direct_generate_async(
    task_dir,
    prompt: str,
    registry: Registry,
    *,
    max_tokens: int = 4096,
) -> str:
    """Direct mode: skip iterations, produce the deliverable in one LLM call."""
    store = TaskStore(task_dir)
    store.ensure_dirs()
    store.touch_last_seen("work")
    logger = JsonlLogger(store.logs_dir, "work")
    logger.decision("direct_start", detail="direct generation mode")

    provider, eff = registry.provider_for("work")
    logger.info("llm_request", detail=f"provider={eff.provider} model={eff.model} direct_mode")
    system = (
        "You are a research and writing agent. Produce a comprehensive, "
        "well-structured document that fully addresses the user's request. "
        "Write in the language of the request. Do NOT ask questions."
    )
    result = await provider.complete(
        system=system,
        messages=[{"role": "user", "content": prompt}],
        model=eff.model,
        max_tokens=max_tokens,
        temperature=0.3,
    )
    logger.info("llm_response", detail=f"chars={len(result.text)}")
    deliverable_path = store.state_dir / "deliverable.md"
    deliverable_path.write_text(result.text, encoding="utf-8")
    store.update_progress(status="done")
    logger.decision("direct_done", detail=f"len={len(result.text)}")
    return result.text


def direct_generate(task_dir, prompt: str, registry: Registry, **kwargs) -> str:
    """Synchronous wrapper for direct generation mode."""
    return asyncio.run(_direct_generate_async(task_dir, prompt, registry, **kwargs))
