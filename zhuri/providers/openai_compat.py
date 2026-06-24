"""OpenAI-compatible Chat Completions provider (§10.2).

Reaches Qwen, Kimi (Moonshot), DeepSeek and any local OpenAI-compatible server
via ``base_url``/``api_key``. Uses ``httpx`` directly — no agent framework.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from .base import AuthError, LLMProvider, ProviderError, ProviderResult


class OpenAICompatProvider(LLMProvider):
    """Chat Completions client for any OpenAI-compatible endpoint."""

    name = "openai_compat"

    def __init__(self, *, base_url: str, api_key: str, timeout: float = 120.0):
        if not base_url:
            raise ProviderError("openai_compat provider requires a base_url")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
        }

    def _payload(self, *, system, messages, model, max_tokens, temperature, tools, stream):
        body: dict = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if tools:
            body["tools"] = tools
        return body

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code in (401, 403):
            raise AuthError(
                f"authentication failed ({resp.status_code}); check the provider api_key"
            )
        if resp.status_code >= 400:
            raise ProviderError(f"provider error {resp.status_code}: {resp.text[:200]}")

    async def complete(self, *, system, messages, model, max_tokens=1024,
                       temperature=0.7, tools=None) -> ProviderResult:
        body = self._payload(system=system, messages=messages, model=model,
                             max_tokens=max_tokens, temperature=temperature,
                             tools=tools, stream=False)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=body,
                )
        except httpx.HTTPError as exc:  # pragma: no cover - network
            raise ProviderError(f"request failed: {exc}") from exc
        self._raise_for_status(resp)
        data = resp.json()
        choice = data["choices"][0]
        msg = choice.get("message", {})
        return ProviderResult(
            text=msg.get("content") or "",
            model=data.get("model", model),
            finish_reason=choice.get("finish_reason", "stop"),
            tool_calls=msg.get("tool_calls", []) or [],
            usage=data.get("usage", {}) or {},
        )

    async def stream(self, *, system, messages, model, max_tokens=1024,
                     temperature=0.7, tools=None) -> AsyncIterator[str]:
        body = self._payload(system=system, messages=messages, model=model,
                             max_tokens=max_tokens, temperature=temperature,
                             tools=tools, stream=True)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions",
                headers=self._headers(), json=body,
            ) as resp:
                self._raise_for_status(resp)
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[len("data:"):].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        payload = json.loads(chunk)
                    except json.JSONDecodeError:  # pragma: no cover
                        continue
                    delta = payload["choices"][0].get("delta", {})
                    if delta.get("content"):
                        yield delta["content"]
