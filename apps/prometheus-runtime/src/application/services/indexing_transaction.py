"""Cross-store consistency between the vector index and the SQLite manifest.

The vector index and the metadata manifest are two independent stores (Architecture.md,
section 17, principle 7) that cannot be committed atomically. This module orders the two
writes so the manifest never claims a Document is indexed unless its vectors are already
durable, and compensates by removing the vectors again when the manifest write fails.
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
    """Write vectors first, then commit the manifest; compensate on a manifest failure.

    Stale points are removed by known chunk ids (no collection-wide payload scan).
    New documents pass an empty ``previous_chunk_ids`` and skip deletion entirely.
    Shared ids between previous and new chunks are left for upsert to overwrite.

    If ``vector_index.upsert`` fails, the manifest is left untouched: the Document keeps
    whatever state it had before, so a retry starts from a clean slate. If the manifest
    commit fails after the vectors were written, the just-written vectors are deleted so
    no unaccounted chunks remain in the vector index.
    """

    new_ids = {chunk.id for chunk in chunks}
    stale_ids = tuple(chunk_id for chunk_id in previous_chunk_ids if chunk_id not in new_ids)
    if stale_ids:
        vector_index.delete_by_ids(stale_ids)
    vector_index.upsert(document, chunks, vectors)
    try:
        with unit_of_work:
            document_repository.save_indexed(document, chunks, indexed_at)
            if lexical_index is not None:
                lexical_index.replace_document(document, chunks)
            unit_of_work.commit()
    except Exception:
        vector_index.delete_by_ids(tuple(chunk.id for chunk in chunks))
        raise


def remove_document_index(
    *,
    document_id: DocumentId,
    vector_index: VectorIndex,
    document_repository: DocumentRepository,
    unit_of_work: UnitOfWork,
    lexical_index: LexicalIndex | None = None,
    chunk_ids: Sequence[ChunkId] = (),
) -> None:
    """Delete vectors, then the manifest row; idempotent for an already-removed Document."""

    if chunk_ids:
        vector_index.delete_by_ids(chunk_ids)
    else:
        vector_index.delete_by_document(document_id)
    with unit_of_work:
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
    """Update vector payload first and compensate if the manifest update fails."""

    vector_index.update_document_path(document_id, new_path)
    try:
        with unit_of_work:
            document_repository.update_path(document_id, new_path)
            if lexical_index is not None:
                lexical_index.update_document_path(document_id, new_path)
            unit_of_work.commit()
    except Exception:
        vector_index.update_document_path(document_id, old_path)
        raise
