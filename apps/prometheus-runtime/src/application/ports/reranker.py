"""Retrieval reranking application port."""

from collections.abc import Sequence
from typing import Protocol

from domain.entities.search_hit import SearchHit


class Reranker(Protocol):
    """Reorder retrieval candidates without exposing model-specific types."""

    def rerank(self, query: str, hits: Sequence[SearchHit]) -> Sequence[SearchHit]: ...
