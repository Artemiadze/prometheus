"""Language-model application port."""

from collections.abc import Sequence
from typing import Protocol


class LanguageModel(Protocol):
    """Generate an answer using only explicitly supplied local context."""

    def generate(
        self,
        question: str,
        context: Sequence[str],
        *,
        temperature: float,
        context_size: int,
    ) -> str: ...

    def list_models(self) -> Sequence[str]: ...

    def is_available(self) -> bool: ...
