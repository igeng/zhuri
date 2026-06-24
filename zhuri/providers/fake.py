"""A deterministic fake provider for tests (§0.1: no real LLM calls).

Not used on the production path; lives in the package so both the test suite and
an ``--offline`` doctor mode can construct it. Scripted responses are keyed by a
substring match on the last user message, with a default fallback.
"""
from __future__ import annotations

from typing import AsyncIterator

from .base import AuthError, LLMProvider, ProviderResult


class FakeProvider(LLMProvider):
    """Record/replay stub honoring the :class:`LLMProvider` contract."""

    name = "openai_compat"

    def __init__(
        self,
        *,
        scripted: dict[str, str] | None = None,
        default: str = "ok: finding recorded with evidence",
        fail_auth: bool = False,
    ):
        self.scripted = scripted or {}
        self.default = default
        self.fail_auth = fail_auth
        self.calls: list[dict] = []

    def _pick(self, system: str, messages: list[dict], model: str) -> str:
        last = messages[-1]["content"] if messages else ""
        for needle, reply in self.scripted.items():
            if needle in last or needle in system:
                return reply
        return self.default

    async def complete(self, *, system, messages, model, max_tokens=1024,
                       temperature=0.7, tools=None) -> ProviderResult:
        if self.fail_auth:
            raise AuthError("fake auth failure")
        self.calls.append({"system": system, "messages": messages, "model": model})
        return ProviderResult(text=self._pick(system, messages, model), model=model)

    async def stream(self, *, system, messages, model, max_tokens=1024,
                     temperature=0.7, tools=None) -> AsyncIterator[str]:
        if self.fail_auth:
            raise AuthError("fake auth failure")
        self.calls.append({"system": system, "messages": messages, "model": model})
        text = self._pick(system, messages, model)
        for token in text.split(" "):
            yield token + " "
