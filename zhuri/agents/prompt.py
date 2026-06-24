"""Prompt assembly (§6.3).

Per SKILL.md §8 every work/subagent prompt MUST include five fields:
background, a verifiable deliverable, working directory, file/line caps, and
completion criteria. :func:`build_prompt` refuses to build a prompt missing any.
"""
from __future__ import annotations

from dataclasses import dataclass

REQUIRED_FIELDS = (
    "background",
    "deliverable",
    "working_dir",
    "caps",
    "completion_criteria",
)


class PromptIncompleteError(ValueError):
    """Raised when a required prompt field is missing/empty (§6.3)."""


@dataclass
class WorkPrompt:
    """Assembled system+user prompt for a work/subagent call."""

    system: str
    user: str


def build_prompt(
    *,
    background: str,
    deliverable: str,
    working_dir: str,
    caps: str,
    completion_criteria: str,
    directions_tried: list[str] | None = None,
    extra: str = "",
) -> WorkPrompt:
    """Assemble a complete work prompt, enforcing the five mandatory fields."""
    values = {
        "background": background,
        "deliverable": deliverable,
        "working_dir": working_dir,
        "caps": caps,
        "completion_criteria": completion_criteria,
    }
    missing = [name for name in REQUIRED_FIELDS if not str(values[name]).strip()]
    if missing:
        raise PromptIncompleteError(
            "prompt missing required field(s): " + ", ".join(missing)
        )

    system = (
        "You are an autonomous zhuri work agent operating under a zero-interaction "
        "protocol (B1). You MUST NOT ask the user questions. If preparation is "
        "complete, EXECUTE — do not stop to ask permission (B2). Record verifiable "
        "findings only."
    )
    tried = directions_tried or []
    tried_block = (
        "Directions already tried (DO NOT repeat the structural axis):\n- "
        + "\n- ".join(tried)
        if tried
        else "No prior directions."
    )
    user = "\n\n".join(
        [
            f"# Background\n{background}",
            f"# Deliverable (must be verifiable)\n{deliverable}",
            f"# Working directory\n{working_dir}",
            f"# File / line caps\n{caps}",
            f"# Completion criteria\n{completion_criteria}",
            f"# {tried_block}",
            *( [extra] if extra.strip() else [] ),
        ]
    )
    return WorkPrompt(system=system, user=user)
