"""Task-pack plugin interface (§SPEC-TODO §三).

Defines the two foundational ABCs that every task pack must implement:

- :class:`SubSkill` — a prompt-builder for one domain-specific capability
- :class:`TaskPack` — a named collection of sub-skills, phase routing, weakness
  routing, quality gates, and a stop condition

All built-in packs (paper_writing, future deep_research, code_analysis, etc.)
are just concrete implementations of these two interfaces. The core engine
(orchestrator / work_agent / watchdog) knows nothing about them beyond the
direction string.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

from zhuri.agents.prompt import WorkPrompt
from zhuri.state.models import Finding, Progress


# ---------------------------------------------------------------------------
# SubSkill — one domain-specific capability
# ---------------------------------------------------------------------------

@dataclass
class SubSkillContext:
    """Curated state injected into a sub-skill's prompt-building method."""

    task_spec: str = ""
    progress: Progress | None = None
    findings: list[Finding] = field(default_factory=list)
    directions_tried: list[str] = field(default_factory=list)
    extra: str = ""


class SubSkill(ABC):
    """A domain-specific capability that builds a complete :class:`WorkPrompt`.

    Each concrete sub-skill encodes expert workflow instructions — stage
    pipelines, scoring rubrics, quality checklists — directly into the prompt
    template.  The work agent receives the prompt and executes it without
    knowing which sub-skill produced it.
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    def build_prompt(self, ctx: SubSkillContext) -> WorkPrompt:
        """Return a fully-formed work prompt for this sub-skill."""
        ...


# ---------------------------------------------------------------------------
# TaskPack — a named collection of sub-skills
# ---------------------------------------------------------------------------

@dataclass
class PhaseRoute:
    name: str
    target: float
    min_iter: int
    max_iter: int


@dataclass(frozen=True)
class WeaknessRoute:
    subskill: str
    action: str


GateResult = tuple[bool, list[str]]
GateFn = Callable[[dict], GateResult]


class TaskPack(ABC):
    """A registered task domain: sub-skills, phase routing, weakness routing,
    quality gates, and a stop condition.

    New domains are added by subclassing and registering in
    ``tasks/__init__.py``.  The orchestrator only needs the pack's name to
    resolve directions like ``"subskill:literature"``.
    """

    name: str = ""
    description: str = ""

    @property
    @abstractmethod
    def sub_skills(self) -> dict[str, SubSkill]:
        """Mapping of direction-key → SubSkill instance."""
        ...

    @abstractmethod
    def phase_for(self, iteration: int) -> PhaseRoute:
        """Return the phase configuration for a given iteration number."""
        ...

    @abstractmethod
    def route_weakness(self, weakness: str) -> WeaknessRoute:
        """Map a reviewer-identified weakness to (subskill, action)."""
        ...

    @abstractmethod
    def quality_gates(self) -> dict[str, GateFn]:
        """Return all quality gates keyed by name."""
        ...

    @abstractmethod
    def should_stop(self, score: float, recent_deltas: list[float],
                    iteration: int) -> bool:
        """Return True when the improvement loop should stop."""
        ...

    def resolve_direction(self, direction: str) -> SubSkill | None:
        """Return the SubSkill for *direction*, or None if unknown."""
        return self.sub_skills.get(direction)

    def direction_names(self) -> list[str]:
        return list(self.sub_skills.keys())


# re-export for convenience
__all__ = [
    "SubSkill",
    "SubSkillContext",
    "TaskPack",
    "PhaseRoute",
    "WeaknessRoute",
    "GateResult",
    "GateFn",
]
