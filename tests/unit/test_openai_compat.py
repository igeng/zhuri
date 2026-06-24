from __future__ import annotations

import asyncio

import httpx
import pytest

from zhuri.providers.base import AuthError, ProviderError
from zhuri.providers.openai_compat import OpenAICompatProvider


def _provider_with(handler):
    p = OpenAICompatProvider(base_url="https://example.test/v1", api_key="k")
    transport = httpx.MockTransport(handler)
    # Patch AsyncClient to use the mock transport.
    orig = httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = transport
        return orig(*a, **kw)

    return p, factory


def test_requires_base_url():
    with pytest.raises(ProviderError):
        OpenAICompatProvider(base_url="", api_key="k")


def test_complete_ok(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={
            "model": "m", "choices": [
                {"message": {"content": "hello"}, "finish_reason": "stop"}
            ], "usage": {"total_tokens": 3},
        })

    p, factory = _provider_with(handler)
    monkeypatch.setattr(httpx, "AsyncClient", factory)
    res = asyncio.run(p.complete(system="s", messages=[{"role": "user", "content": "x"}], model="m"))
    assert res.text == "hello" and res.usage["total_tokens"] == 3


def test_auth_error(monkeypatch):
    def handler(request):
        return httpx.Response(401, text="nope")

    p, factory = _provider_with(handler)
    monkeypatch.setattr(httpx, "AsyncClient", factory)
    with pytest.raises(AuthError) as ei:
        asyncio.run(p.complete(system="s", messages=[], model="m"))
    assert ei.value.exit_code == 3


def test_generic_error(monkeypatch):
    def handler(request):
        return httpx.Response(500, text="boom")

    p, factory = _provider_with(handler)
    monkeypatch.setattr(httpx, "AsyncClient", factory)
    with pytest.raises(ProviderError):
        asyncio.run(p.complete(system="s", messages=[], model="m"))


def test_stream(monkeypatch):
    body = (
        'data: {"choices":[{"delta":{"content":"he"}}]}\n'
        'data: {"choices":[{"delta":{"content":"llo"}}]}\n'
        "data: [DONE]\n"
    )

    def handler(request):
        return httpx.Response(200, text=body)

    p, factory = _provider_with(handler)
    monkeypatch.setattr(httpx, "AsyncClient", factory)

    async def collect():
        return "".join([t async for t in p.stream(system="s", messages=[], model="m")])

    assert asyncio.run(collect()) == "hello"


def test_tools_included(monkeypatch):
    captured = {}

    def handler(request):
        import json
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "model": "m", "choices": [{"message": {"content": "ok", "tool_calls": [{"id": "1"}]}, "finish_reason": "tool_calls"}],
        })

    p, factory = _provider_with(handler)
    monkeypatch.setattr(httpx, "AsyncClient", factory)
    res = asyncio.run(p.complete(system="s", messages=[], model="m", tools=[{"type": "function"}]))
    assert captured["body"]["tools"]
    assert res.tool_calls
