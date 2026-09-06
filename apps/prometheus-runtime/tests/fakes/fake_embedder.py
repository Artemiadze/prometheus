"""Deterministic in-memory Embedder for unit tests."""

import hashlib
from collections.abc import Sequence

from domain.entities.chunk import Chunk
from domain.entities.document import normalize_content


class FakeEmbedder:
    """Generate stable vectors without loading a model."""

    def __init__(self, dimension: int = 8, model_id: str = "fake-embedder") -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension
        self._model_id = model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_id(self) -> str:
        return self._model_id

    def _embed(self, text: str) -> tuple[float, ...]:
        seed = normalize_content(text).encode("utf-8")
        values = bytearray()
        counter = 0
        while len(values) < self.dimension:
            values.extend(hashlib.sha256(seed + counter.to_bytes(4)).digest())
            counter += 1
        return tuple((value - 127.5) / 127.5 for value in values[: self.dimension])

    def embed_documents(self, chunks: Sequence[Chunk]) -> Sequence[Sequence[float]]:
        return tuple(self._embed(chunk.text) for chunk in chunks)

    def embed_query(self, text: str) -> Sequence[float]:
        return self._embed(text)
