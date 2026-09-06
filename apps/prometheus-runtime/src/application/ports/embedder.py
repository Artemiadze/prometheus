"""Embedding application port."""

from collections.abc import Sequence
from typing import Protocol

from domain.entities.chunk import Chunk


class Embedder(Protocol):
    """Generate deterministic vectors without exposing provider-specific types."""

    @property
    def dimension(self) -> int: ...

    @property
    def model_id(self) -> str: ...

    def embed_documents(self, chunks: Sequence[Chunk]) -> Sequence[Sequence[float]]: ...

    def embed_query(self, text: str) -> Sequence[float]: ...
