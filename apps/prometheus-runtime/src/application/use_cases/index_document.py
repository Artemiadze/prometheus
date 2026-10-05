"""Index one document through application ports."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

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
from application.services.index_fingerprint import ensure_index_compatible
from application.services.index_generation import IndexGeneration
from application.services.indexing_transaction import replace_document_index
from application.use_cases.rename_document import RenameDocument
from domain.entities.chunk import Chunk
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
        self._clock = clock

    async def execute(
        self,
        document: Document,
        *,
        force: bool = False,
    ) -> IndexDocumentResult:
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
        vectors = await self._embed_chunks(document, chunks, state is not None)
        replace_document_index(
            document=document,
            chunks=chunks,
            vectors=vectors,
            indexed_at=self._clock(),
            vector_index=self._vectors,
            document_repository=self._documents,
            unit_of_work=self._unit_of_work,
            lexical_index=self._lexical,
        )
        if stored_fingerprint is None and not force:
            self._metadata.save(self._fingerprint)
        if self._index_generation is not None:
            self._index_generation.bump()
        return IndexDocumentResult(
            document.id,
            created_chunks=len(chunks),
            deleted_chunks=0 if state is None else state.chunk_count,
        )

    async def _embed_chunks(
        self,
        document: Document,
        chunks: tuple[Chunk, ...],
        had_prior_index: bool,
    ) -> tuple[Sequence[float], ...]:
        old_by_index = {}
        if had_prior_index:
            old_by_index = {
                fingerprint.chunk_index: fingerprint
                for fingerprint in self._documents.list_chunk_fingerprints(document.id)
            }
        reuse_ids = [
            old_by_index[chunk.chunk_index].chunk_id
            for chunk in chunks
            if chunk.chunk_index in old_by_index
            and old_by_index[chunk.chunk_index].content_hash == chunk.content_hash
        ]
        cached = self._vectors.retrieve_vectors(reuse_ids) if reuse_ids else {}

        vectors: list[Sequence[float] | None] = [None] * len(chunks)
        embed_batch: list[Chunk] = []
        embed_positions: list[int] = []
        for index, chunk in enumerate(chunks):
            old = old_by_index.get(chunk.chunk_index)
            if (
                old is not None
                and old.content_hash == chunk.content_hash
                and old.chunk_id.value in cached
            ):
                vectors[index] = cached[old.chunk_id.value]
                continue
            embed_batch.append(chunk)
            embed_positions.append(index)

        if embed_batch:
            async with self._compute_gate.exclusive("background"):
                embedded = await asyncio.to_thread(self._embedder.embed_documents, embed_batch)
            for position, vector in zip(embed_positions, embedded, strict=True):
                vectors[position] = vector

        filled: list[Sequence[float]] = []
        for slot in vectors:
            if slot is None:
                raise DocumentTooLargeError()
            filled.append(slot)
        return tuple(filled)
