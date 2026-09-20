"""Index one document through application ports."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from application.dto.index_fingerprint import IndexFingerprint
from application.dto.indexing import IndexDocumentResult
from application.errors import DocumentTooLargeError, RevisionConflictError, VaultMismatchError
from application.ports.chunker import Chunker
from application.ports.document_repository import DocumentRepository
from application.ports.embedder import Embedder
from application.ports.index_metadata_store import IndexMetadataStore
from application.ports.markdown_parser import MarkdownParser
from application.ports.unit_of_work import UnitOfWork
from application.ports.vector_index import VectorIndex
from application.services.index_fingerprint import ensure_index_compatible
from application.services.indexing_transaction import replace_document_index
from application.use_cases.rename_document import RenameDocument
from domain.entities.document import Document, normalize_content
from domain.value_objects.vault_id import VaultId


class IndexDocument:
    def __init__(
        self,
        *,
        vault_id: VaultId,
        parser: MarkdownParser,
        chunker: Chunker,
        embedder: Embedder,
        vector_index: VectorIndex,
        document_repository: DocumentRepository,
        unit_of_work: UnitOfWork,
        index_metadata_store: IndexMetadataStore,
        active_fingerprint: IndexFingerprint,
        rename_document: RenameDocument,
        max_document_chars: int,
        max_chunks_per_document: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._vault_id = vault_id
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._vectors = vector_index
        self._documents = document_repository
        self._unit_of_work = unit_of_work
        self._metadata = index_metadata_store
        self._fingerprint = active_fingerprint
        self._rename = rename_document
        self._max_document_chars = max_document_chars
        self._max_chunks_per_document = max_chunks_per_document
        self._clock = clock

    async def execute(
        self,
        document: Document,
        *,
        force: bool = False,
    ) -> IndexDocumentResult:
        if document.vault_id != self._vault_id:
            raise VaultMismatchError()
        if len(normalize_content(document.content)) > self._max_document_chars:
            raise DocumentTooLargeError()
        state = self._documents.get_state(document.id)
        if state is not None and document.revision < state.revision:
            raise RevisionConflictError()
        if not force and state is not None and state.content_hash == document.content_hash:
            if state.relative_path != document.relative_path:
                return await self._rename.execute(document.id, document.relative_path)
            return IndexDocumentResult(document.id, 0, 0, skipped=True)

        stored_fingerprint = self._metadata.load()
        if not force:
            ensure_index_compatible(stored_fingerprint, self._fingerprint)
        chunks = tuple(self._chunker.chunk(self._parser.parse(document)))
        if len(chunks) > self._max_chunks_per_document:
            raise DocumentTooLargeError()
        vectors = self._embedder.embed_documents(chunks)
        replace_document_index(
            document=document,
            chunks=chunks,
            vectors=vectors,
            indexed_at=self._clock(),
            vector_index=self._vectors,
            document_repository=self._documents,
            unit_of_work=self._unit_of_work,
        )
        if stored_fingerprint is None and not force:
            self._metadata.save(self._fingerprint)
        return IndexDocumentResult(
            document.id,
            created_chunks=len(chunks),
            deleted_chunks=0 if state is None else state.chunk_count,
        )
