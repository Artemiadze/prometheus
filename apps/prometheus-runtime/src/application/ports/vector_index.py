"""Vector-index application port."""

from collections.abc import Mapping, Sequence
from typing import Protocol

from application.dto.index_status import IndexStatus
from domain.entities.chunk import Chunk
from domain.entities.document import Document
from domain.entities.search_hit import SearchHit
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import SearchScope


class VectorIndex(Protocol):
    """Store and retrieve vectors within one already-scoped Vault."""

    @property
    def status(self) -> IndexStatus: ...

    def upsert(
        self,
        document: Document,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None: ...

    def retrieve_vectors(self, chunk_ids: Sequence[ChunkId]) -> Mapping[str, Sequence[float]]: ...

    def delete_by_document(self, document_id: DocumentId) -> None: ...

    def update_document_path(
        self,
        document_id: DocumentId,
        relative_path: RelativePath,
    ) -> None: ...

    def search(
        self,
        query_vector: Sequence[float],
        limit: int,
        scope: SearchScope | None = None,
    ) -> Sequence[SearchHit]: ...
