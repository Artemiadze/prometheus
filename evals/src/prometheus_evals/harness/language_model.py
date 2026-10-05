"""Deterministic extractive LLM for offline RAG evals."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence

from application.dto.llm import LlmGeneration, LocalLlmModel

_FRAGMENT = re.compile(
    r"\[\d+\] Source: [^\n]+\n(.*?)(?=\n\n\[|\n\nQuestion:|\Z)",
    re.DOTALL,
)
_NO_CONTEXT = "No context fragments were included."
_REFUSAL = "There is not enough information in the user's notes."


class ExtractiveEvalLanguageModel:
    """Return a short extract from the best context fragment or a grounded refusal."""

    def __init__(self, model_name: str = "eval-extractive-v1") -> None:
        self._model_name = model_name
        self.calls: list[tuple[str, str]] = []

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
        del temperature, context_size, max_output_tokens, response_schema
        self.calls.append((system, user))
        return LlmGeneration(_structured_answer(user), self._model_name)

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
        generation = await self.generate(
            system,
            user,
            temperature=temperature,
            context_size=context_size,
            max_output_tokens=max_output_tokens,
            response_schema=response_schema,
        )
        yield generation.text

    async def list_models(self) -> Sequence[LocalLlmModel]:
        return (LocalLlmModel(self._model_name, 0),)

    async def is_available(self) -> bool:
        return True


def _structured_answer(user: str) -> str:
    if _NO_CONTEXT in user:
        return json.dumps({"answer": _REFUSAL, "sources": []}, ensure_ascii=False)
    fragments = [part.strip() for part in _FRAGMENT.findall(user) if part.strip()]
    if not fragments:
        return json.dumps({"answer": _REFUSAL, "sources": []}, ensure_ascii=False)
    best = max(fragments, key=len)
    sentence = best.split(".")[0].strip()
    if not sentence:
        sentence = best[:200].strip()
    return json.dumps({"answer": sentence, "sources": [1]}, ensure_ascii=False)
