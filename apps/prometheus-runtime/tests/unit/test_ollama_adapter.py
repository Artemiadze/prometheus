"""Contract tests for the asynchronous local Ollama adapter (PRM-42/43/45)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine

import httpx
import pytest
from httpx._content import AsyncIteratorByteStream

from adapters.outbound.ollama.adapter import OllamaLanguageModel
from adapters.outbound.ollama.errors import (
    LlmContextExceededError,
    LlmModelNotFoundError,
    LlmTimeoutError,
    OllamaUnavailableError,
)
from application.dto.llm import LlmGeneration, LocalLlmModel

_Handler = Callable[[httpx.Request], Coroutine[None, None, httpx.Response]]


def _run_with_client[T](
    handler: _Handler,
    operation: Callable[[OllamaLanguageModel], Awaitable[T]],
) -> T:
    async def run() -> T:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = OllamaLanguageModel(
                base_url="http://127.0.0.1:11434",
                model="qwen3:4b",
                timeout_seconds=120,
                client=client,
            )
            return await operation(adapter)

    return asyncio.run(run())


def test_generate_sends_expected_options_and_returns_typed_result() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://127.0.0.1:11434/api/generate"
        payload = json.loads(request.content)
        assert payload == {
            "model": "qwen3:4b",
            "prompt": "Grounded prompt",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 8192,
                "num_predict": 1024,
            },
        }
        return httpx.Response(
            200,
            json={
                "model": "qwen3:4b",
                "response": "Grounded answer",
                "prompt_eval_count": 42,
                "eval_count": 12,
                "done_reason": "stop",
            },
        )

    async def generate(adapter: OllamaLanguageModel) -> LlmGeneration:
        return await adapter.generate(
            "Grounded prompt",
            temperature=0.1,
            context_size=8192,
            max_output_tokens=1024,
        )

    result = _run_with_client(handler, generate)

    assert result == LlmGeneration("Grounded answer", "qwen3:4b", 42, 12, "stop")


def test_list_models_returns_only_local_models_with_available_metadata() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "qwen3:4b",
                        "size": 2_500,
                        "details": {"quantization_level": "Q4_K_M"},
                    },
                    {
                        "name": "remote:latest",
                        "size": 0,
                        "remote_model": "remote",
                        "remote_host": "https://example.invalid",
                    },
                    {"model": "gemma3:4b", "size": 3_300},
                ]
            },
        )

    models = _run_with_client(handler, lambda adapter: adapter.list_models())

    assert models == (
        LocalLlmModel("gemma3:4b", 3_300),
        LocalLlmModel("qwen3:4b", 2_500, "Q4_K_M"),
    )


def test_empty_local_model_catalog_still_means_ollama_is_available() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": []})

    assert _run_with_client(handler, lambda adapter: adapter.is_available())


def test_unavailable_ollama_is_an_error_for_listing_but_false_for_probe() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private host detail", request=request)

    async def check(adapter: OllamaLanguageModel) -> tuple[str, bool]:
        with pytest.raises(OllamaUnavailableError) as caught:
            await adapter.list_models()
        return str(caught.value), await adapter.is_available()

    message, available = _run_with_client(handler, check)

    assert not available
    assert "private host detail" not in message


@pytest.mark.parametrize(
    ("status", "body", "expected_error"),
    [
        (404, {"error": "model 'qwen3:4b' not found"}, LlmModelNotFoundError),
        (400, {"error": "prompt exceeds context length"}, LlmContextExceededError),
        (500, {"error": "private server response"}, OllamaUnavailableError),
    ],
)
def test_generate_maps_http_failures_without_leaking_response(
    status: int,
    body: dict[str, str],
    expected_error: type[Exception],
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    async def generate(adapter: OllamaLanguageModel) -> str:
        with pytest.raises(expected_error) as caught:
            await adapter.generate(
                "private prompt",
                temperature=0.1,
                context_size=8192,
                max_output_tokens=1024,
            )
        return str(caught.value)

    message = _run_with_client(handler, generate)

    assert "private prompt" not in message
    assert body["error"] not in message


def test_generate_maps_transport_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private timeout detail", request=request)

    async def generate(adapter: OllamaLanguageModel) -> None:
        with pytest.raises(LlmTimeoutError) as caught:
            await adapter.generate(
                "private prompt",
                temperature=0.1,
                context_size=8192,
                max_output_tokens=1024,
            )
        assert "private" not in str(caught.value)

    _run_with_client(handler, generate)


@pytest.mark.parametrize(
    "path",
    ["/api/generate", "/api/tags"],
)
def test_malformed_ollama_json_is_not_exposed(path: str) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"private malformed response")

    async def call(adapter: OllamaLanguageModel) -> None:
        with pytest.raises(OllamaUnavailableError) as caught:
            if path.endswith("generate"):
                await adapter.generate(
                    "private prompt",
                    temperature=0.1,
                    context_size=8192,
                    max_output_tokens=1024,
                )
            else:
                await adapter.list_models()
        assert "private" not in str(caught.value)

    _run_with_client(handler, call)


def test_stream_yields_response_fragments_in_order() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert payload["model"] == "qwen3:4b"

        async def body() -> AsyncIterator[bytes]:
            yield b'{"response":"Hello","done":false}\n'
            yield b'{"response":" world","done":false}\n'
            yield b'{"done":true}\n'

        return httpx.Response(200, stream=AsyncIteratorByteStream(body()))

    async def collect(adapter: OllamaLanguageModel) -> str:
        parts: list[str] = []
        async for piece in adapter.stream(
            "Grounded prompt",
            temperature=0.1,
            context_size=8192,
            max_output_tokens=1024,
        ):
            parts.append(piece)
        return "".join(parts)

    text = _run_with_client(handler, collect)
    assert text == "Hello world"


def test_stream_maps_http_failures_like_generate() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'qwen3:4b' not found"})

    async def consume(adapter: OllamaLanguageModel) -> None:
        with pytest.raises(LlmModelNotFoundError):
            async for _ in adapter.stream(
                "private prompt",
                temperature=0.1,
                context_size=8192,
                max_output_tokens=1024,
            ):
                pass

    _run_with_client(handler, consume)


def test_cancelling_generation_propagates_asyncio_cancellation() -> None:
    started = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = OllamaLanguageModel(
                base_url="http://localhost:11434/api",
                model="qwen3:4b",
                timeout_seconds=120,
                client=client,
            )
            task = asyncio.create_task(
                adapter.generate(
                    "Grounded prompt",
                    temperature=0.1,
                    context_size=8192,
                    max_output_tokens=1024,
                )
            )
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run())


@pytest.mark.parametrize(
    "base_url",
    ["https://api.example.com", "http://192.168.1.10:11434", "file:///tmp/ollama"],
)
def test_adapter_rejects_non_loopback_or_non_http_hosts(base_url: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        OllamaLanguageModel(
            base_url=base_url,
            model="qwen3:4b",
            timeout_seconds=120,
        )
