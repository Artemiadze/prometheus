"""Predictable local LanguageModel fake."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from application.dto.llm import LlmGeneration, LocalLlmModel


class FakeLanguageModel:
    """Echo questions and context while recording generation calls."""

    def __init__(
        self,
        models: Sequence[LocalLlmModel] = (LocalLlmModel("fake-model", 0),),
        *,
        available: bool = True,
        stream_parts: Sequence[str] | None = None,
        stream_pause_after_first: asyncio.Event | None = None,
    ) -> None:
        self.models = tuple(models)
        self.available = available
        self.calls: list[tuple[str, float, int, int]] = []
        self.stream_calls: list[tuple[str, float, int, int]] = []
        self.stream_parts = stream_parts
        self.stream_pause_after_first = stream_pause_after_first
        self.stream_closed = False

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float,
        context_size: int,
        max_output_tokens: int,
    ) -> LlmGeneration:
        self.calls.append((prompt, temperature, context_size, max_output_tokens))
        model = self.models[0].name if self.models else "fake-model"
        return LlmGeneration(prompt, model)

    async def stream(
        self,
        prompt: str,
        *,
        temperature: float,
        context_size: int,
        max_output_tokens: int,
    ) -> AsyncIterator[str]:
        self.stream_calls.append((prompt, temperature, context_size, max_output_tokens))
        parts = self.stream_parts if self.stream_parts is not None else (prompt,)
        try:
            for index, part in enumerate(parts):
                if index == 1 and self.stream_pause_after_first is not None:
                    await self.stream_pause_after_first.wait()
                yield part
        finally:
            self.stream_closed = True

    async def list_models(self) -> Sequence[LocalLlmModel]:
        return self.models

    async def is_available(self) -> bool:
        return self.available
