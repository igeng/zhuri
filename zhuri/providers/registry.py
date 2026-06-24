"""Role → provider/model routing and per-round model rotation (§10.5).

Builds concrete :class:`LLMProvider` instances from resolved config roles, and
supports a deterministic (seedable) model pool rotation so at least one agent can
be forced onto a different model each round (peer-review anti-inflation, direction
diversity).
"""
from __future__ import annotations

import os
from typing import Callable

from ..config import Config, EffectiveAgent
from .base import LLMProvider
from .openai_compat import OpenAICompatProvider

ProviderFactory = Callable[[EffectiveAgent], LLMProvider]


def _default_factory(eff: EffectiveAgent) -> LLMProvider:
    # Deterministic offline/test seam (§0.1): when ZHURI_FAKE_PROVIDER is set,
    # use the in-process fake provider instead of a network call. This keeps the
    # production path on openai_compat (§10.2) while letting real `zhuri work`
    # subprocesses run without a live LLM endpoint.
    if os.environ.get("ZHURI_FAKE_PROVIDER"):
        from .fake import FakeProvider

        return FakeProvider(default=os.environ.get("ZHURI_FAKE_TEXT", "FINDING: a :: b\nDONE"))
    # v1 ships exactly one provider type: openai_compat (§10.2).
    return OpenAICompatProvider(base_url=eff.base_url, api_key=eff.api_key)


class Registry:
    """Resolve agent roles to provider instances and rotate model pools."""

    def __init__(self, config: Config, *, factory: ProviderFactory | None = None):
        self.config = config
        self.factory = factory or _default_factory

    def resolve(self, role: str) -> EffectiveAgent:
        return self.config.resolve_role(role)

    def provider_for(self, role: str) -> tuple[LLMProvider, EffectiveAgent]:
        eff = self.resolve(role)
        return self.factory(eff), eff

    def model_for_round(self, role: str, rnd: int) -> str:
        """Deterministically pick a model from the role's pool for a round.

        Rotation is ``pool[round % len(pool)]`` — stable for reproducibility and
        guaranteed to differ across consecutive rounds when the pool has >1 model.
        """
        eff = self.resolve(role)
        pool = eff.models or [eff.model]
        return pool[rnd % len(pool)]

    def diverse_model(self, role: str, rnd: int, *, avoid: str | None = None) -> str:
        """Pick a model different from ``avoid`` when the pool allows it."""
        eff = self.resolve(role)
        pool = eff.models or [eff.model]
        if avoid is None or len(pool) == 1:
            return self.model_for_round(role, rnd)
        candidates = [m for m in pool if m != avoid] or pool
        return candidates[rnd % len(candidates)]
