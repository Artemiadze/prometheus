"""Embedding application port."""

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    """Generate deterministic vectors without exposing provider-specific types."""

    @property
    def dimension(self) -> int: ...

    @property
    def model_id(self) -> str: ...

    def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...

    def embed_query(self, text: str) -> Sequence[float]: ...
