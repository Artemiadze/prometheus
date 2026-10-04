"""Predictable local LanguageModel fake."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence

from application.dto.llm import LlmGeneration, LocalLlmModel

_FRAGMENT = re.compile(
    r"\[\d+\] Source: [^\n]+\n(.*?)(?=\n\n\[|\n\nQuestion:|\Z)",
    re.DOTALL,
)


class FakeLanguageModel:
    """Echo grounded user context while recording generation calls."""

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
        self.calls: list[tuple[str, str, float, int, int, Mapping[str, object] | None]] = []
        self.stream_calls: list[tuple[str, str, float, int, int, Mapping[str, object] | None]] = []
        self.stream_parts = stream_parts
        self.stream_pause_after_first = stream_pause_after_first
        self.stream_closed = False

    async def generate(
        self,
        system: str,
        user: str,
        *,
        temperature: float,
        context_size: int,
        max_output_tokens: int,
        response_schema: Mapping[str, object] | None = None,
    ) -> LlmGeneration:
        self.calls.append(
            (
                system,
                user,
                temperature,
                context_size,
                max_output_tokens,
                response_schema,
            ),
        )
        model = self.models[0].name if self.models else "fake-model"
        return LlmGeneration(_structured_answer(user), model)

    async def stream(
        self,
        system: str,
        user: str,
        *,
        temperature: float,
        context_size: int,
        max_output_tokens: int,
        response_schema: Mapping[str, object] | None = None,
    ) -> AsyncIterator[str]:
        self.stream_calls.append(
            (
                system,
                user,
                temperature,
                context_size,
                max_output_tokens,
                response_schema,
            ),
        )
        parts = self.stream_parts if self.stream_parts is not None else (_structured_answer(user),)
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


def _structured_answer(user: str) -> str:
    if "No context fragments were included." in user:
        answer = "There is not enough information in the user's notes."
        sources: list[int] = []
    else:
        fragments = [part.strip() for part in _FRAGMENT.findall(user) if part.strip()]
        if not fragments:
            answer = "There is not enough information in the user's notes."
            sources = []
        else:
            best = max(fragments, key=len)
            sentence = best.split(".")[0].strip() or best[:200].strip()
            answer = sentence
            sources = [1]
    return json.dumps({"answer": answer, "sources": sources}, ensure_ascii=False)
