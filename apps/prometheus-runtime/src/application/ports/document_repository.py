"""Document manifest persistence application port."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from application.dto.document_state import DocumentState
from domain.entities.chunk import Chunk
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath


class DocumentRepository(Protocol):
    """Read and update manifest state within one already-scoped Vault.

    Note text and chunk content are never stored here; the manifest only tracks
    identity, hashes, and indexing bookkeeping so it can be safely rebuilt from the
    Vault and the vector index.
    """

    def get_state(self, document_id: DocumentId) -> DocumentState | None: ...

    def list_states(self) -> Sequence[DocumentState]: ...

    def list_relative_paths(self) -> Sequence[RelativePath]: ...

    def save_indexed(
        self,
        document: Document,
        chunks: Sequence[Chunk],
        indexed_at: datetime,
    ) -> None: ...

    def update_path(
        self,
        document_id: DocumentId,
        relative_path: RelativePath,
    ) -> None: ...

    def delete(self, document_id: DocumentId) -> None: ...
