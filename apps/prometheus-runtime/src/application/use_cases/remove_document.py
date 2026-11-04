"""Idempotently remove one indexed document."""

from application.dto.indexing import RemoveDocumentResult
from application.ports.document_repository import DocumentRepository
from application.ports.lexical_index import LexicalIndex
from application.ports.unit_of_work import UnitOfWork
from application.ports.vector_index import VectorIndex
from application.services.index_generation import IndexGeneration
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
        index_generation: IndexGeneration | None = None,
    ) -> None:
        self._documents = document_repository
        self._vectors = vector_index
        self._lexical = lexical_index
        self._unit_of_work = unit_of_work
        self._index_generation = index_generation

    async def execute(self, document_id: DocumentId) -> RemoveDocumentResult:
        state = self._documents.get_state(document_id)
        if state is None:
            return RemoveDocumentResult(document_id, removed=False, removed_chunks=0)
        chunk_ids = tuple(
            fingerprint.chunk_id
            for fingerprint in self._documents.list_chunk_fingerprints(document_id)
        )
        remove_document_index(
            document_id=document_id,
            vector_index=self._vectors,
            document_repository=self._documents,
            unit_of_work=self._unit_of_work,
            lexical_index=self._lexical,
            chunk_ids=chunk_ids,
        )
        if self._index_generation is not None:
            self._index_generation.bump()
        return RemoveDocumentResult(document_id, removed=True, removed_chunks=state.chunk_count)
