"""In-memory DocumentRepository for unit tests."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime

from application.dto.document_state import DocumentState
from domain.entities.chunk import Chunk
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath


class FakeDocumentRepository:
    """Store manifest state in a dictionary scoped to one test Vault."""

    def __init__(self, states: Iterable[DocumentState] = ()) -> None:
        self._states: dict[DocumentId, DocumentState] = {
            state.document_id: state for state in states
        }

    def get_state(self, document_id: DocumentId) -> DocumentState | None:
        return self._states.get(document_id)

    def list_states(self) -> Sequence[DocumentState]:
        return tuple(sorted(self._states.values(), key=lambda state: state.relative_path.value))

    def list_relative_paths(self) -> Sequence[RelativePath]:
        return tuple(state.relative_path for state in self.list_states())

    def save_indexed(
        self,
        document: Document,
        chunks: Sequence[Chunk],
        indexed_at: datetime,
    ) -> None:
        """Persist manifest state derived from a successfully indexed Document."""

        self._states[document.id] = DocumentState(
            document_id=document.id,
            relative_path=document.relative_path,
            revision=document.revision,
            content_hash=document.content_hash,
            modified_at=document.modified_at,
            indexed_at=indexed_at,
            chunk_count=len(chunks),
        )

    def update_path(
        self,
        document_id: DocumentId,
        relative_path: RelativePath,
    ) -> None:
        state = self._states.get(document_id)
        if state is None:
            return
        self._states[document_id] = DocumentState(
            document_id=state.document_id,
            relative_path=relative_path,
            revision=state.revision,
            content_hash=state.content_hash,
            modified_at=state.modified_at,
            indexed_at=state.indexed_at,
            chunk_count=state.chunk_count,
        )

    def delete(self, document_id: DocumentId) -> None:
        """Remove state in a test setup; missing IDs are a no-op."""

        self._states.pop(document_id, None)
