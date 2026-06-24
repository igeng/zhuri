"""LLM provider ABC (§10.3).

Providers are called **directly** — no agent framework wraps them (A9). The ABC
supports streaming, optional tool/function calling, and per-call model selection.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


class ProviderError(Exception):
    """Generic provider failure → exit code 1."""

    exit_code = 1


class AuthError(ProviderError):
    """Authentication/authorization failure → exit code 3 (§10.3)."""

    exit_code = 3


@dataclass
class ProviderResult:
    """Result of a single completion call."""

    text: str
    model: str
    finish_reason: str = "stop"
    tool_calls: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)

    def ends_with_question(self) -> bool:
        """B1 stall signal: a work-path answer that ends on a question."""
        stripped = self.text.strip()
        return stripped.endswith("?") or stripped.endswith("？")


class LLMProvider(ABC):
    """Abstract OpenAI-style chat provider."""

    name: str = "base"

    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        messages: list[dict],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        tools: list | None = None,
    ) -> ProviderResult:
        """Return a full completion (collecting any stream internally)."""

    @abstractmethod
    async def stream(
        self,
        *,
        system: str,
        messages: list[dict],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        tools: list | None = None,
    ) -> AsyncIterator[str]:
        """Yield text deltas for TTY streaming."""
        raise NotImplementedError
        yield  # pragma: no cover
