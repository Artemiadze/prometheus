"""Index one document through application ports."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from application.dto.chunk_fingerprint import ChunkFingerprint
from application.dto.index_fingerprint import IndexFingerprint
from application.dto.indexing import IndexDocumentResult
from application.errors import (
    DocumentTooLargeError,
    PathIgnoredError,
    RevisionConflictError,
    VaultMismatchError,
)
from application.ports.chunker import Chunker
from application.ports.document_repository import DocumentRepository
from application.ports.embedder import Embedder
from application.ports.index_metadata_store import IndexMetadataStore
from application.ports.lexical_index import LexicalIndex
from application.ports.markdown_parser import MarkdownParser
from application.ports.unit_of_work import UnitOfWork
from application.ports.vault_settings_store import VaultSettingsStore
from application.ports.vector_index import VectorIndex
from application.services.compute_gate import ComputeGate
from application.services.embedding_reuse import (
    ResolvedEmbeddings,
    fill_resolved_embeddings,
    resolve_reusable_embeddings,
)
from application.services.index_fingerprint import ensure_index_compatible
from application.services.index_generation import IndexGeneration
from application.services.indexing_transaction import replace_document_index
from application.use_cases.rename_document import RenameDocument
from domain.entities.chunk import Chunk
from domain.entities.document import Document, normalize_content
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.vault_id import VaultId


@dataclass(frozen=True, slots=True)
class PreparedDocumentIndex:
    """Document ready for embedding + manifest write."""

    document: Document
    chunks: tuple[Chunk, ...]
    previous_chunk_ids: tuple[ChunkId, ...]
    reuse_fingerprints: tuple[ChunkFingerprint, ...]
    stored_fingerprint: IndexFingerprint | None
    force: bool
    prior_chunk_count: int


class IndexDocument:
    def __init__(
        self,
        *,
        vault_id: VaultId,
        parser: MarkdownParser,
        chunker: Chunker,
        embedder: Embedder,
        vector_index: VectorIndex,
        lexical_index: LexicalIndex | None,
        document_repository: DocumentRepository,
        unit_of_work: UnitOfWork,
        index_metadata_store: IndexMetadataStore,
        active_fingerprint: IndexFingerprint,
        rename_document: RenameDocument,
        max_document_chars: int,
        max_chunks_per_document: int,
        vault_settings_store: VaultSettingsStore | None = None,
        compute_gate: ComputeGate | None = None,
        index_generation: IndexGeneration | None = None,
        reuse_document_repository: DocumentRepository | None = None,
        reuse_vector_index: VectorIndex | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._vault_id = vault_id
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._vectors = vector_index
        self._lexical = lexical_index
        self._documents = document_repository
        self._unit_of_work = unit_of_work
        self._metadata = index_metadata_store
        self._fingerprint = active_fingerprint
        self._rename = rename_document
        self._max_document_chars = max_document_chars
        self._max_chunks_per_document = max_chunks_per_document
        self._vault_settings = vault_settings_store
        self._compute_gate = compute_gate or ComputeGate()
        self._index_generation = index_generation
        self._reuse_documents = reuse_document_repository
        self._reuse_vectors = reuse_vector_index
        self._clock = clock

    async def execute(
        self,
        document: Document,
        *,
        force: bool = False,
    ) -> IndexDocumentResult:
        prepared = await self.prepare(document, force=force)
        if isinstance(prepared, IndexDocumentResult):
            return prepared
        resolved = self.resolve_embeddings(prepared)
        vectors = await self.complete_embeddings(resolved)
        return self.commit(prepared, vectors)

    async def prepare(
        self,
        document: Document,
        *,
        force: bool = False,
    ) -> PreparedDocumentIndex | IndexDocumentResult:
        if document.vault_id != self._vault_id:
            raise VaultMismatchError()
        if self._vault_settings is not None and self._vault_settings.load_ignored_folders().covers(
            document.relative_path
        ):
            raise PathIgnoredError()
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

        previous_fingerprints = (
            tuple(self._documents.list_chunk_fingerprints(document.id)) if state is not None else ()
        )
        reuse_source = self._reuse_documents or self._documents
        if reuse_source is self._documents:
            reuse_fingerprints = previous_fingerprints
        else:
            reuse_fingerprints = tuple(reuse_source.list_chunk_fingerprints(document.id))

        return PreparedDocumentIndex(
            document=document,
            chunks=chunks,
            previous_chunk_ids=tuple(fingerprint.chunk_id for fingerprint in previous_fingerprints),
            reuse_fingerprints=reuse_fingerprints,
            stored_fingerprint=stored_fingerprint,
            force=force,
            prior_chunk_count=0 if state is None else state.chunk_count,
        )

    def resolve_embeddings(self, prepared: PreparedDocumentIndex) -> ResolvedEmbeddings:
        vector_source = self._reuse_vectors or self._vectors
        return resolve_reusable_embeddings(
            prepared.chunks,
            prepared.reuse_fingerprints,
            vector_source,
        )

    async def embed_batch(self, chunks: Sequence[Chunk]) -> Sequence[Sequence[float]]:
        if not chunks:
            return ()
        async with self._compute_gate.exclusive("background"):
            return await asyncio.to_thread(self._embedder.embed_documents, chunks)

    async def complete_embeddings(
        self,
        resolved: ResolvedEmbeddings,
    ) -> tuple[Sequence[float], ...]:
        if resolved.complete:
            return fill_resolved_embeddings(resolved, ())
        embedded = await self.embed_batch(resolved.missing_chunks)
        return fill_resolved_embeddings(resolved, embedded)

    def commit(
        self,
        prepared: PreparedDocumentIndex,
        vectors: Sequence[Sequence[float]],
    ) -> IndexDocumentResult:
        if len(vectors) != len(prepared.chunks):
            raise ValueError("vectors must align with prepared chunks")
        replace_document_index(
            document=prepared.document,
            chunks=prepared.chunks,
            vectors=vectors,
            indexed_at=self._clock(),
            vector_index=self._vectors,
            document_repository=self._documents,
            unit_of_work=self._unit_of_work,
            lexical_index=self._lexical,
            previous_chunk_ids=prepared.previous_chunk_ids,
        )
        if prepared.stored_fingerprint is None and not prepared.force:
            self._metadata.save(self._fingerprint)
        if self._index_generation is not None:
            self._index_generation.bump()
        return IndexDocumentResult(
            prepared.document.id,
            created_chunks=len(prepared.chunks),
            deleted_chunks=prepared.prior_chunk_count,
        )
