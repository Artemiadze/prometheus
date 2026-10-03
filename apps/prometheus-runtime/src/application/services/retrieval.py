"""Shared retrieval component for semantic search and grounded answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from application.dto.index_fingerprint import IndexFingerprint
from application.errors import QueryTooShortError, VaultNotIndexedError
from application.ports.document_repository import DocumentRepository
from application.ports.embedder import Embedder
from application.ports.index_metadata_store import IndexMetadataStore
from application.ports.lexical_index import LexicalIndex
from application.ports.reranker import Reranker
from application.ports.vault_settings_store import VaultSettingsStore
from application.ports.vector_index import VectorIndex
from application.services.hybrid_fusion import fuse_weighted_rrf
from application.services.index_fingerprint import ensure_index_compatible
from domain.entities.search_hit import SearchHit
from domain.errors import AdapterNotConfiguredError
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import SearchScope

RetrievalMode = Literal["dense", "hybrid"]


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
        active_fingerprint: IndexFingerprint,
        reranker: Reranker | None = None,
        lexical_index: LexicalIndex | None = None,
        retrieval_mode: RetrievalMode = "dense",
        hybrid_rrf_k: int = 60,
        hybrid_dense_weight: float = 1.0,
        hybrid_lexical_weight: float = 1.0,
        hybrid_candidate_multiplier: int = 2,
        minimum_query_length: int = 3,
        top_k: int = 10,
        rerank_candidate_limit: int = 20,
        vault_settings_store: VaultSettingsStore | None = None,
    ) -> None:
        self._embedder = embedder
        self._vectors = vector_index
        self._documents = document_repository
        self._metadata = index_metadata_store
        self._fingerprint = active_fingerprint
        self._reranker = reranker
        self._lexical = lexical_index
        self._retrieval_mode = retrieval_mode
        self._hybrid_rrf_k = hybrid_rrf_k
        self._hybrid_dense_weight = hybrid_dense_weight
        self._hybrid_lexical_weight = hybrid_lexical_weight
        self._hybrid_candidate_multiplier = hybrid_candidate_multiplier
        self._minimum_query_length = minimum_query_length
        self._top_k = top_k
        self._rerank_candidate_limit = rerank_candidate_limit
        self._vault_settings = vault_settings_store
        if retrieval_mode == "hybrid" and lexical_index is None:
            raise AdapterNotConfiguredError(
                "lexical_index adapter is not configured; hybrid retrieval requires FTS"
            )

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
        stored = self._metadata.load()
        if stored is None:
            raise VaultNotIndexedError()
        ensure_index_compatible(stored, self._fingerprint)
        effective_scope = self._effective_scope(scope)
        vector = self._embedder.embed_query(normalized)
        candidate_limit = self._candidate_limit(limit)
        if self._retrieval_mode == "dense":
            hits = tuple(self._vectors.search(vector, candidate_limit, effective_scope))
        else:
            pool = max(candidate_limit, max(limit, self._top_k) * self._hybrid_candidate_multiplier)
            dense_hits = tuple(self._vectors.search(vector, pool, effective_scope))
            lexical_hits = tuple(self._lexical.search(normalized, pool, effective_scope))  # type: ignore[union-attr]
            hits = fuse_weighted_rrf(
                dense_hits,
                lexical_hits,
                k=self._hybrid_rrf_k,
                dense_weight=self._hybrid_dense_weight,
                lexical_weight=self._hybrid_lexical_weight,
            )[:pool]
        if self._reranker is not None:
            hits = tuple(self._reranker.rerank(normalized, hits))[:limit]
        else:
            hits = hits[:limit]
        results = []
        for hit in hits:
            state = self._documents.get_state(hit.chunk.document_id)
            if state is not None:
                results.append(RetrievedHit(hit, state.relative_path))
        return tuple(results)

    def _candidate_limit(self, limit: int) -> int:
        if self._reranker is None:
            return limit
        return max(limit, self._rerank_candidate_limit)

    def _effective_scope(self, scope: SearchScope | None) -> SearchScope | None:
        if self._vault_settings is None:
            return scope
        ignored = self._vault_settings.load_ignored_folders()
        if not ignored.folders:
            return scope
        exclusions = ignored.as_relative_paths()
        if scope is None:
            return SearchScope.entire_vault().with_exclusions(exclusions)
        return scope.with_exclusions(exclusions)
