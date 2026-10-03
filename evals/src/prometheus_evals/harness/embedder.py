"""Deterministic lexical embedder for offline retrieval evals."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

from application.dto.embedding import EmbeddingFingerprint
from domain.entities.chunk import Chunk
from domain.entities.document import normalize_content

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class HashedBagOfWordsEmbedder:
    """Map token hashes into a fixed-size bag-of-words vector for stable cosine scores."""

    def __init__(
        self,
        *,
        dimension: int = 256,
        model_id: str = "eval-bow-v1",
        provider: str = "eval",
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension
        self._model_id = model_id
        self._provider = provider

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def fingerprint(self) -> EmbeddingFingerprint:
        return EmbeddingFingerprint(self.provider, self.model_id, self.dimension)

    def embed_documents(self, chunks: Sequence[Chunk]) -> Sequence[Sequence[float]]:
        return tuple(self._embed(chunk.text) for chunk in chunks)

    def embed_query(self, text: str) -> Sequence[float]:
        return self._embed(text)

    def _embed(self, text: str) -> tuple[float, ...]:
        normalized = normalize_content(text).casefold()
        vector = [0.0] * self._dimension
        for token in _TOKEN.findall(normalized):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return tuple(0.0 for _ in range(self._dimension))
        return tuple(value / norm for value in vector)
