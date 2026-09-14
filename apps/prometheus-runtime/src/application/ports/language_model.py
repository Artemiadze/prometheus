"""Language-model application port."""

from collections.abc import Sequence
from typing import Protocol

from application.dto.llm import LlmGeneration, LocalLlmModel


class LanguageModel(Protocol):
    """Generate an answer using only explicitly supplied local context."""

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float,
        context_size: int,
        max_output_tokens: int,
    ) -> LlmGeneration: ...

    async def list_models(self) -> Sequence[LocalLlmModel]: ...

    async def is_available(self) -> bool: ...
