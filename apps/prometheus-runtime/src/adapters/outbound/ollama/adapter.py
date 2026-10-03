"""Asynchronous LanguageModel adapter for a loopback-only Ollama runtime."""

from __future__ import annotations

import ipaddress
import json
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from adapters.outbound.ollama.errors import (
    LlmContextExceededError,
    LlmModelNotFoundError,
    LlmTimeoutError,
    OllamaUnavailableError,
)
from application.dto.llm import LlmGeneration, LocalLlmModel

_CONTEXT_ERROR_MARKERS = (
    "context length",
    "context window",
    "context size",
    "num_ctx",
    "too large",
)
_MODEL_ERROR_MARKERS = ("model", "not found")


class OllamaLanguageModel:
    """Generate text and enumerate models through Ollama's local HTTP API."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = _normalize_loopback_url(base_url)
        self._model = model.strip()
        if not self._model:
            raise ValueError("model cannot be blank")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout_seconds),
        )

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float,
        context_size: int,
        max_output_tokens: int,
    ) -> LlmGeneration:
        """Generate a typed result; cancellation propagates as ``CancelledError``."""

        if not prompt.strip():
            raise ValueError("prompt cannot be blank")
        if context_size <= 0 or max_output_tokens <= 0:
            raise ValueError("LLM token limits must be positive")
        try:
            response = await self._client.post(
                f"{self._base_url}/api/generate",
                json=_generation_payload(
                    model=self._model,
                    prompt=prompt,
                    stream=False,
                    temperature=temperature,
                    context_size=context_size,
                    max_output_tokens=max_output_tokens,
                ),
            )
        except httpx.TimeoutException as error:
            raise LlmTimeoutError() from error
        except httpx.NetworkError as error:
            raise OllamaUnavailableError() from error

        _raise_generation_error(response)
        try:
            payload = _json_object(response)
            return LlmGeneration(
                text=_required_string(payload, "response"),
                model=_optional_string(payload, "model") or self._model,
                prompt_tokens=_optional_integer(payload, "prompt_eval_count"),
                completion_tokens=_optional_integer(payload, "eval_count"),
                done_reason=_optional_string(payload, "done_reason"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise OllamaUnavailableError() from error

    async def stream(
        self,
        prompt: str,
        *,
        temperature: float,
        context_size: int,
        max_output_tokens: int,
    ) -> AsyncIterator[str]:
        """Yield response fragments; closing the iterator cancels Ollama generation."""

        if not prompt.strip():
            raise ValueError("prompt cannot be blank")
        if context_size <= 0 or max_output_tokens <= 0:
            raise ValueError("LLM token limits must be positive")
        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/api/generate",
                json=_generation_payload(
                    model=self._model,
                    prompt=prompt,
                    stream=True,
                    temperature=temperature,
                    context_size=context_size,
                    max_output_tokens=max_output_tokens,
                ),
            ) as response:
                _raise_generation_error(response)
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except ValueError as error:
                        raise OllamaUnavailableError() from error
                    if not isinstance(payload, Mapping):
                        raise OllamaUnavailableError()
                    if payload.get("done"):
                        break
                    piece = payload.get("response")
                    if isinstance(piece, str) and piece:
                        yield piece
        except httpx.TimeoutException as error:
            raise LlmTimeoutError() from error
        except httpx.NetworkError as error:
            raise OllamaUnavailableError() from error

    async def list_models(self) -> Sequence[LocalLlmModel]:
        """Return only models physically installed in the configured Ollama."""

        try:
            response = await self._client.get(f"{self._base_url}/api/tags")
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise OllamaUnavailableError() from error
        if not response.is_success:
            raise OllamaUnavailableError()

        try:
            payload = _json_object(response)
            raw_models = payload["models"]
            if not isinstance(raw_models, list):
                raise TypeError
            models = tuple(
                model
                for item in raw_models
                if isinstance(item, Mapping)
                and not _is_remote_model(item)
                and (model := _local_model(item)) is not None
            )
        except (KeyError, TypeError, ValueError) as error:
            raise OllamaUnavailableError() from error
        return tuple(sorted(models, key=lambda model: model.name.casefold()))

    async def is_available(self) -> bool:
        """Return availability without confusing an empty local catalog with failure."""

        try:
            await self.list_models()
        except OllamaUnavailableError:
            return False
        return True

    async def aclose(self) -> None:
        """Close the internally owned HTTP client."""

        if self._owns_client:
            await self._client.aclose()


def _generation_payload(
    *,
    model: str,
    prompt: str,
    stream: bool,
    temperature: float,
    context_size: int,
    max_output_tokens: int,
) -> dict[str, object]:
    return {
        "model": model,
        "prompt": prompt,
        "stream": stream,
        "options": {
            "temperature": temperature,
            "num_ctx": context_size,
            "num_predict": max_output_tokens,
        },
    }


def _normalize_loopback_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "http" or parsed.hostname is None or parsed.query or parsed.fragment:
        raise ValueError("Ollama URL must be an HTTP loopback URL")
    try:
        is_loopback = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        is_loopback = parsed.hostname.casefold() == "localhost"
    if not is_loopback:
        raise ValueError("Ollama URL must be an HTTP loopback URL")
    path = parsed.path.rstrip("/")
    if path == "/api":
        path = ""
    elif path:
        raise ValueError("Ollama URL must not contain a path")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _raise_generation_error(response: httpx.Response) -> None:
    if response.is_success:
        return
    message = _safe_error_text(response).casefold()
    if response.status_code == 404 or all(marker in message for marker in _MODEL_ERROR_MARKERS):
        raise LlmModelNotFoundError()
    if response.status_code in {400, 413} and any(
        marker in message for marker in _CONTEXT_ERROR_MARKERS
    ):
        raise LlmContextExceededError()
    raise OllamaUnavailableError()


def _safe_error_text(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, Mapping):
        return ""
    error = payload.get("error")
    return error if isinstance(error, str) else ""


def _json_object(response: httpx.Response) -> Mapping[str, Any]:
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise TypeError
    return payload


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise TypeError
    return value


def _optional_string(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError
    return value


def _optional_integer(payload: Mapping[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TypeError
    return int(value)


def _is_remote_model(payload: Mapping[str, Any]) -> bool:
    return any(
        isinstance(payload.get(key), str) and bool(payload[key].strip())
        for key in ("remote_model", "remote_host")
    )


def _local_model(payload: Mapping[str, Any]) -> LocalLlmModel | None:
    name = payload.get("name", payload.get("model"))
    if not isinstance(name, str) or not name.strip():
        return None
    size = payload.get("size", 0)
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise TypeError
    details = payload.get("details")
    quantization: str | None = None
    if details is not None:
        if not isinstance(details, Mapping):
            raise TypeError
        raw_quantization = details.get("quantization_level")
        if raw_quantization is not None and not isinstance(raw_quantization, str):
            raise TypeError
        quantization = raw_quantization
    return LocalLlmModel(name=name, size_bytes=size, quantization=quantization)
