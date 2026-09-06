"""Embedding application port."""

from collections.abc import Sequence
from typing import Protocol

from application.dto.embedding import EmbeddingFingerprint
from domain.entities.chunk import Chunk


class Embedder(Protocol):
    """Generate deterministic vectors without exposing provider-specific types."""

    @property
    def provider(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    @property
    def model_id(self) -> str: ...

    @property
    def fingerprint(self) -> EmbeddingFingerprint: ...

    def embed_documents(self, chunks: Sequence[Chunk]) -> Sequence[Sequence[float]]: ...

    def embed_query(self, text: str) -> Sequence[float]: ...
