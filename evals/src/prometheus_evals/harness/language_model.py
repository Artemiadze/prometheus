"""Deterministic extractive LLM for offline RAG evals."""

from __future__ import annotations

import re
from collections.abc import Sequence

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
        self.calls: list[str] = []

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float,
        context_size: int,
        max_output_tokens: int,
    ) -> LlmGeneration:
        del temperature, context_size, max_output_tokens
        self.calls.append(prompt)
        if _NO_CONTEXT in prompt:
            return LlmGeneration(_REFUSAL, self._model_name)
        fragments = [part.strip() for part in _FRAGMENT.findall(prompt) if part.strip()]
        if not fragments:
            return LlmGeneration(_REFUSAL, self._model_name)
        best = max(fragments, key=len)
        sentence = best.split(".")[0].strip()
        if not sentence:
            sentence = best[:200].strip()
        return LlmGeneration(sentence, self._model_name)

    async def list_models(self) -> Sequence[LocalLlmModel]:
        return (LocalLlmModel(self._model_name, 0),)

    async def is_available(self) -> bool:
        return True
