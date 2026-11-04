"""Transactional consistency between the vector index and the SQLite manifest.

Vectors, document/chunk rows, and the lexical index share one SQLite connection, so a
single UnitOfWork commit covers the full document replace/remove/relocate path.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from application.ports.document_repository import DocumentRepository
from application.ports.lexical_index import LexicalIndex
from application.ports.unit_of_work import UnitOfWork
from application.ports.vector_index import VectorIndex
from domain.entities.chunk import Chunk
from domain.entities.document import Document
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath


def replace_document_index(
    *,
    document: Document,
    chunks: Sequence[Chunk],
    vectors: Sequence[Sequence[float]],
    indexed_at: datetime,
    vector_index: VectorIndex,
    document_repository: DocumentRepository,
    unit_of_work: UnitOfWork,
    lexical_index: LexicalIndex | None = None,
    previous_chunk_ids: Sequence[ChunkId] = (),
) -> None:
    """Atomically replace vectors and manifest rows for one document.

    Stale points are removed by known chunk ids. Shared ids between previous and new
    chunks are left for upsert to overwrite. New documents pass an empty
    ``previous_chunk_ids`` and skip deletion entirely.
    """

    new_ids = {chunk.id for chunk in chunks}
    stale_ids = tuple(chunk_id for chunk_id in previous_chunk_ids if chunk_id not in new_ids)
    with unit_of_work:
        if stale_ids:
            vector_index.delete_by_ids(stale_ids)
        vector_index.upsert(document, chunks, vectors)
        document_repository.save_indexed(document, chunks, indexed_at)
        if lexical_index is not None:
            lexical_index.replace_document(document, chunks)
        unit_of_work.commit()


def remove_document_index(
    *,
    document_id: DocumentId,
    vector_index: VectorIndex,
    document_repository: DocumentRepository,
    unit_of_work: UnitOfWork,
    lexical_index: LexicalIndex | None = None,
    chunk_ids: Sequence[ChunkId] = (),
) -> None:
    """Delete vectors and the manifest row; idempotent for an already-removed Document."""

    with unit_of_work:
        if chunk_ids:
            vector_index.delete_by_ids(chunk_ids)
        else:
            vector_index.delete_by_document(document_id)
        if lexical_index is not None:
            lexical_index.delete_by_document(document_id)
        document_repository.delete(document_id)
        unit_of_work.commit()


def relocate_document_index(
    *,
    document_id: DocumentId,
    old_path: RelativePath,
    new_path: RelativePath,
    vector_index: VectorIndex,
    document_repository: DocumentRepository,
    unit_of_work: UnitOfWork,
    lexical_index: LexicalIndex | None = None,
) -> None:
    """Update path metadata for one document inside a single transaction."""

    del old_path  # retained in signature for call-site compatibility
    with unit_of_work:
        vector_index.update_document_path(document_id, new_path)
        document_repository.update_path(document_id, new_path)
        if lexical_index is not None:
            lexical_index.update_document_path(document_id, new_path)
        unit_of_work.commit()
