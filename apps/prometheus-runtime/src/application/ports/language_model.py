"""Language-model application port."""

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Protocol

from application.dto.llm import LlmGeneration, LocalLlmModel


class LanguageModel(Protocol):
    """Generate an answer using only explicitly supplied local context."""

    async def generate(
        self,
        system: str,
        user: str,
        *,
        temperature: float,
        context_size: int,
        max_output_tokens: int,
        response_schema: Mapping[str, object] | None = None,
    ) -> LlmGeneration: ...

    def stream(
        self,
        system: str,
        user: str,
        *,
        temperature: float,
        context_size: int,
        max_output_tokens: int,
        response_schema: Mapping[str, object] | None = None,
    ) -> AsyncIterator[str]: ...

    async def list_models(self) -> Sequence[LocalLlmModel]: ...

    async def is_available(self) -> bool: ...
