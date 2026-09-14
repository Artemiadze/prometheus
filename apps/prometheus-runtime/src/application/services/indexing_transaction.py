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
from application.ports.unit_of_work import UnitOfWork
from application.ports.vector_index import VectorIndex
from domain.entities.chunk import Chunk
from domain.entities.document import Document
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
) -> None:
    """Write vectors first, then commit the manifest; compensate on a manifest failure.

    If ``vector_index.upsert`` fails, the manifest is left untouched: the Document keeps
    whatever state it had before, so a retry starts from a clean slate. If the manifest
    commit fails after the vectors were written, the just-written vectors are deleted so
    no unaccounted chunks remain in the vector index.
    """

    vector_index.upsert(document, chunks, vectors)
    try:
        with unit_of_work:
            document_repository.save_indexed(document, chunks, indexed_at)
            unit_of_work.commit()
    except Exception:
        vector_index.delete_by_document(document.id)
        raise


def remove_document_index(
    *,
    document_id: DocumentId,
    vector_index: VectorIndex,
    document_repository: DocumentRepository,
    unit_of_work: UnitOfWork,
) -> None:
    """Delete vectors, then the manifest row; idempotent for an already-removed Document."""

    vector_index.delete_by_document(document_id)
    with unit_of_work:
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
) -> None:
    """Update vector payload first and compensate if the manifest update fails."""

    vector_index.update_document_path(document_id, new_path)
    try:
        with unit_of_work:
            document_repository.update_path(document_id, new_path)
            unit_of_work.commit()
    except Exception:
        vector_index.update_document_path(document_id, old_path)
        raise
