"""Idempotently remove one indexed document."""

from application.dto.indexing import RemoveDocumentResult
from application.ports.document_repository import DocumentRepository
from application.ports.lexical_index import LexicalIndex
from application.ports.unit_of_work import UnitOfWork
from application.ports.vector_index import VectorIndex
from application.services.indexing_transaction import remove_document_index
from domain.value_objects.document_id import DocumentId


class RemoveDocument:
    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_index: VectorIndex,
        lexical_index: LexicalIndex | None,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._documents = document_repository
        self._vectors = vector_index
        self._lexical = lexical_index
        self._unit_of_work = unit_of_work

    async def execute(self, document_id: DocumentId) -> RemoveDocumentResult:
        state = self._documents.get_state(document_id)
        if state is None:
            return RemoveDocumentResult(document_id, removed=False, removed_chunks=0)
        remove_document_index(
            document_id=document_id,
            vector_index=self._vectors,
            document_repository=self._documents,
            unit_of_work=self._unit_of_work,
            lexical_index=self._lexical,
        )
        return RemoveDocumentResult(document_id, removed=True, removed_chunks=state.chunk_count)
