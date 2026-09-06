"""In-memory VectorIndex with pure-Python cosine search."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from domain.entities.chunk import Chunk
from domain.entities.search_hit import SearchHit, sort_by_score
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import ScopeMode, SearchScope


class FakeVectorIndex:
    """Vault-scoped vector index for deterministic use-case tests."""

    def __init__(
        self,
        document_paths: Mapping[DocumentId, RelativePath] | None = None,
    ) -> None:
        self._documents: dict[
            DocumentId,
            tuple[tuple[Chunk, ...], tuple[tuple[float, ...], ...]],
        ] = {}
        self.document_paths = dict(document_paths or {})

    def upsert(
        self,
        document_id: DocumentId,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if any(chunk.document_id != document_id for chunk in chunks):
            raise ValueError("all chunks must belong to document_id")
        self._documents[document_id] = (
            tuple(chunks),
            tuple(tuple(vector) for vector in vectors),
        )

    def delete_by_document(self, document_id: DocumentId) -> None:
        self._documents.pop(document_id, None)

    def search(
        self,
        query_vector: Sequence[float],
        limit: int,
        scope: SearchScope | None = None,
    ) -> Sequence[SearchHit]:
        if limit < 0:
            raise ValueError("limit cannot be negative")
        hits: list[SearchHit] = []
        for document_id, (chunks, vectors) in self._documents.items():
            if not self._matches_scope(document_id, scope):
                continue
            for chunk, vector in zip(chunks, vectors, strict=True):
                score = self._cosine(query_vector, vector)
                hits.append(SearchHit(chunk=chunk, score=score, dense_score=score))
        return sort_by_score(hits)[:limit]

    def _matches_scope(
        self,
        document_id: DocumentId,
        scope: SearchScope | None,
    ) -> bool:
        if scope is None or scope.mode is ScopeMode.ENTIRE_VAULT:
            return True
        path = self.document_paths.get(document_id)
        if path is None:
            return False
        if scope.mode is ScopeMode.CURRENT_NOTE:
            return path == scope.note
        return any(
            path.value == folder.value or path.value.startswith(f"{folder.value}/")
            for folder in scope.folders
        )

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
        if len(left) != len(right):
            raise ValueError("vector dimensions must match")
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)
