"""Rename an indexed document without recalculating embeddings."""

from application.dto.indexing import IndexDocumentResult
from application.ports.document_repository import DocumentRepository
from application.ports.lexical_index import LexicalIndex
from application.ports.unit_of_work import UnitOfWork
from application.ports.vault_settings_store import VaultSettingsStore
from application.ports.vector_index import VectorIndex
from application.services.indexing_transaction import relocate_document_index
from application.use_cases.remove_document import RemoveDocument
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath


class RenameDocument:
    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        vector_index: VectorIndex,
        lexical_index: LexicalIndex | None,
        unit_of_work: UnitOfWork,
        vault_settings_store: VaultSettingsStore | None = None,
        remove_document: RemoveDocument | None = None,
    ) -> None:
        self._documents = document_repository
        self._vectors = vector_index
        self._lexical = lexical_index
        self._unit_of_work = unit_of_work
        self._vault_settings = vault_settings_store
        self._remove = remove_document

    async def execute(
        self,
        document_id: DocumentId,
        relative_path: RelativePath,
    ) -> IndexDocumentResult:
        state = self._documents.get_state(document_id)
        if state is None:
            return IndexDocumentResult(document_id, 0, 0, skipped=True)
        if state.relative_path == relative_path:
            return IndexDocumentResult(document_id, 0, 0, skipped=True)
        if (
            self._vault_settings is not None
            and self._remove is not None
            and self._vault_settings.load_ignored_folders().covers(relative_path)
        ):
            await self._remove.execute(document_id)
            return IndexDocumentResult(document_id, 0, state.chunk_count, deleted=True)
        relocate_document_index(
            document_id=document_id,
            old_path=state.relative_path,
            new_path=relative_path,
            vector_index=self._vectors,
            document_repository=self._documents,
            unit_of_work=self._unit_of_work,
            lexical_index=self._lexical,
        )
        return IndexDocumentResult(document_id, 0, 0, relocated=True)
