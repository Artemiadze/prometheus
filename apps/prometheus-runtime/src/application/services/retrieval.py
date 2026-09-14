"""Shared retrieval component for semantic search and grounded answers."""

from __future__ import annotations

from dataclasses import dataclass

from application.errors import QueryTooShortError, VaultNotIndexedError
from application.ports.document_repository import DocumentRepository
from application.ports.embedder import Embedder
from application.ports.index_metadata_store import IndexMetadataStore
from application.ports.reranker import Reranker
from application.ports.vector_index import VectorIndex
from domain.entities.search_hit import SearchHit
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import SearchScope


@dataclass(frozen=True, slots=True)
class RetrievedHit:
    hit: SearchHit
    relative_path: RelativePath


class RetrievalService:
    def __init__(
        self,
        *,
        embedder: Embedder,
        vector_index: VectorIndex,
        document_repository: DocumentRepository,
        index_metadata_store: IndexMetadataStore,
        reranker: Reranker | None = None,
        minimum_query_length: int = 3,
    ) -> None:
        self._embedder = embedder
        self._vectors = vector_index
        self._documents = document_repository
        self._metadata = index_metadata_store
        self._reranker = reranker
        self._minimum_query_length = minimum_query_length

    async def retrieve(
        self,
        query: str,
        *,
        scope: SearchScope | None = None,
        limit: int,
    ) -> tuple[RetrievedHit, ...]:
        normalized = query.strip()
        if len(normalized) < self._minimum_query_length:
            raise QueryTooShortError()
        if self._metadata.load() is None:
            raise VaultNotIndexedError()
        vector = self._embedder.embed_query(normalized)
        hits = tuple(self._vectors.search(vector, limit, scope))
        if self._reranker is not None:
            hits = tuple(self._reranker.rerank(normalized, hits))[:limit]
        results = []
        for hit in hits:
            state = self._documents.get_state(hit.chunk.document_id)
            if state is not None:
                results.append(RetrievedHit(hit, state.relative_path))
        return tuple(results)
