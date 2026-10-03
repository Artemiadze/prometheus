"""Integration: Ollama adapter against an HTTP contract stub (PRM-81)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine

import httpx
import pytest
from httpx._content import AsyncIteratorByteStream

from adapters.outbound.ollama.adapter import OllamaLanguageModel
from adapters.outbound.ollama.errors import LlmModelNotFoundError, OllamaUnavailableError

pytestmark = pytest.mark.integration

_Handler = Callable[[httpx.Request], Coroutine[None, None, httpx.Response]]


def _run[T](handler: _Handler, operation: Callable[[OllamaLanguageModel], Awaitable[T]]) -> T:
    async def run() -> T:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = OllamaLanguageModel(
                base_url="http://127.0.0.1:11434",
                model="qwen3:4b",
                timeout_seconds=5,
                client=client,
            )
            return await operation(adapter)

    return asyncio.run(run())


def test_stub_lists_models_without_requiring_real_ollama() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={"models": [{"name": "qwen3:4b", "size": 1, "digest": "abc", "details": {}}]},
        )

    models = _run(handler, lambda adapter: adapter.list_models())
    assert [model.name for model in models] == ["qwen3:4b"]


def test_stub_generate_returns_typed_generation() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3:4b"
        assert payload["stream"] is False
        return httpx.Response(
            200,
            json={"response": "stubbed answer", "model": "qwen3:4b", "done": True},
        )

    generation = _run(
        handler,
        lambda adapter: adapter.generate(
            "prompt",
            temperature=0.1,
            context_size=2048,
            max_output_tokens=128,
        ),
    )
    assert generation.text == "stubbed answer"
    assert generation.model == "qwen3:4b"


def test_stub_stream_returns_incremental_tokens() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True

        async def body() -> AsyncIterator[bytes]:
            yield b'{"response":"stub","done":false}\n'
            yield b'{"done":true}\n'

        return httpx.Response(200, stream=AsyncIteratorByteStream(body()))

    async def collect(adapter: OllamaLanguageModel) -> str:
        parts: list[str] = []
        async for piece in adapter.stream(
            "prompt",
            temperature=0.1,
            context_size=2048,
            max_output_tokens=128,
        ):
            parts.append(piece)
        return "".join(parts)

    assert _run(handler, collect) == "stub"


def test_stub_model_not_found_and_unavailable() -> None:
    async def not_found(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'missing' not found"})

    with pytest.raises(LlmModelNotFoundError):
        _run(
            not_found,
            lambda adapter: adapter.generate(
                "prompt",
                temperature=0.1,
                context_size=2048,
                max_output_tokens=128,
            ),
        )

    async def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(OllamaUnavailableError):
        _run(down, lambda adapter: adapter.list_models())
