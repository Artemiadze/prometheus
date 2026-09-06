"""Vector-index application port."""

from collections.abc import Sequence
from typing import Protocol

from domain.entities.chunk import Chunk
from domain.entities.search_hit import SearchHit
from domain.value_objects.document_id import DocumentId
from domain.value_objects.search_scope import SearchScope


class VectorIndex(Protocol):
    """Store and retrieve vectors within one already-scoped Vault."""

    def upsert(
        self,
        document_id: DocumentId,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None: ...

    def delete_by_document(self, document_id: DocumentId) -> None: ...

    def search(
        self,
        query_vector: Sequence[float],
        limit: int,
        scope: SearchScope | None = None,
    ) -> Sequence[SearchHit]: ...
