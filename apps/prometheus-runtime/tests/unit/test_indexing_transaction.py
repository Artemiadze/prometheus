"""Tests for single-transaction indexing between vectors and the manifest."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from application.services.indexing_transaction import (
    remove_document_index,
    replace_document_index,
)
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document, compute_content_hash
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId
from fakes import FakeDocumentRepository, FakeUnitOfWork, FakeVectorIndex


class _FailingVectorIndex(FakeVectorIndex):
    """Fail every ``upsert`` before touching any state."""

    def upsert(
        self,
        document: Document,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        raise RuntimeError("vector store unavailable")


class _FailingDocumentRepository(FakeDocumentRepository):
    """Fail every ``save_indexed`` without recording any new state."""

    def save_indexed(
        self,
        document: Document,
        chunks: Sequence[Chunk],
        indexed_at: datetime,
    ) -> None:
        raise RuntimeError("disk full")


def _document() -> Document:
    return Document.create(
        id=DocumentId("document-01"),
        vault_id=VaultId("vault-01"),
        relative_path="Notes/One.md",
        content="Body text",
        revision=1,
        modified_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _chunk(document: Document, text: str = "chunk text") -> Chunk:
    return Chunk(
        id=ChunkId.from_parts(document.id, ("Section",), 1, 0),
        document_id=document.id,
        text=text,
        heading_path=("Section",),
        chunk_index=0,
        char_range=CharRange(0, len(text)),
        token_count=max(1, len(text.split())),
        content_hash=compute_content_hash(text),
        heading_line=0,
        heading_occurrence=1,
    )


def test_replace_document_index_writes_vectors_and_manifest_in_one_uow() -> None:
    vector_index = FakeVectorIndex()
    repository = FakeDocumentRepository()
    unit_of_work = FakeUnitOfWork()
    document = _document()
    chunk = _chunk(document)
    indexed_at = datetime(2026, 1, 2, tzinfo=UTC)

    replace_document_index(
        document=document,
        chunks=(chunk,),
        vectors=((1.0, 0.0),),
        indexed_at=indexed_at,
        vector_index=vector_index,
        document_repository=repository,
        unit_of_work=unit_of_work,
    )

    state = repository.get_state(document.id)
    assert state is not None
    assert state.indexed_at == indexed_at
    hits = vector_index.search((1.0, 0.0), limit=10)
    assert [hit.chunk for hit in hits] == [chunk]
    assert unit_of_work.committed


def test_replace_document_index_rolls_back_uow_when_manifest_fails() -> None:
    vector_index = FakeVectorIndex()
    repository = _FailingDocumentRepository()
    unit_of_work = FakeUnitOfWork()
    document = _document()
    chunk = _chunk(document)

    with pytest.raises(RuntimeError, match="disk full"):
        replace_document_index(
            document=document,
            chunks=(chunk,),
            vectors=((1.0, 0.0),),
            indexed_at=datetime(2026, 1, 2, tzinfo=UTC),
            vector_index=vector_index,
            document_repository=repository,
            unit_of_work=unit_of_work,
        )

    assert repository.get_state(document.id) is None
    assert unit_of_work.rolled_back
    assert unit_of_work.entered


def test_replace_document_index_deletes_only_stale_previous_chunk_ids() -> None:
    vector_index = FakeVectorIndex()
    repository = FakeDocumentRepository()
    document = _document()
    kept = _chunk(document, "kept")
    stale = Chunk(
        id=ChunkId.from_parts(document.id, ("Section",), 1, 1),
        document_id=document.id,
        text="stale",
        heading_path=("Section",),
        chunk_index=1,
        char_range=CharRange(0, 5),
        token_count=1,
        content_hash=compute_content_hash("stale"),
        heading_line=0,
        heading_occurrence=1,
    )
    replace_document_index(
        document=document,
        chunks=(kept, stale),
        vectors=((1.0, 0.0), (0.0, 1.0)),
        indexed_at=datetime(2026, 1, 2, tzinfo=UTC),
        vector_index=vector_index,
        document_repository=repository,
        unit_of_work=FakeUnitOfWork(),
    )

    replace_document_index(
        document=document,
        chunks=(kept,),
        vectors=((1.0, 0.0),),
        indexed_at=datetime(2026, 1, 3, tzinfo=UTC),
        vector_index=vector_index,
        document_repository=repository,
        unit_of_work=FakeUnitOfWork(),
        previous_chunk_ids=(kept.id, stale.id),
    )

    hits = vector_index.search((1.0, 0.0), limit=10)
    assert [hit.chunk for hit in hits] == [kept]


def test_replace_document_index_skips_delete_for_new_documents() -> None:
    class TrackingVectorIndex(FakeVectorIndex):
        def __init__(self) -> None:
            super().__init__()
            self.delete_by_ids_calls: list[tuple[ChunkId, ...]] = []

        def delete_by_ids(self, chunk_ids: Sequence[ChunkId]) -> None:
            self.delete_by_ids_calls.append(tuple(chunk_ids))
            super().delete_by_ids(chunk_ids)

    vector_index = TrackingVectorIndex()
    document = _document()
    chunk = _chunk(document)
    replace_document_index(
        document=document,
        chunks=(chunk,),
        vectors=((1.0, 0.0),),
        indexed_at=datetime(2026, 1, 2, tzinfo=UTC),
        vector_index=vector_index,
        document_repository=FakeDocumentRepository(),
        unit_of_work=FakeUnitOfWork(),
        previous_chunk_ids=(),
    )

    assert vector_index.delete_by_ids_calls == []


def test_replace_document_index_leaves_manifest_untouched_when_vectors_fail() -> None:
    vector_index = _FailingVectorIndex()
    repository = FakeDocumentRepository()
    unit_of_work = FakeUnitOfWork()
    document = _document()
    chunk = _chunk(document)

    with pytest.raises(RuntimeError, match="vector store unavailable"):
        replace_document_index(
            document=document,
            chunks=(chunk,),
            vectors=((1.0, 0.0),),
            indexed_at=datetime(2026, 1, 2, tzinfo=UTC),
            vector_index=vector_index,
            document_repository=repository,
            unit_of_work=unit_of_work,
        )

    assert repository.get_state(document.id) is None
    assert unit_of_work.entered
    assert unit_of_work.rolled_back


def test_remove_document_index_deletes_vectors_and_manifest() -> None:
    vector_index = FakeVectorIndex()
    repository = FakeDocumentRepository()
    unit_of_work = FakeUnitOfWork()
    document = _document()
    chunk = _chunk(document)
    replace_document_index(
        document=document,
        chunks=(chunk,),
        vectors=((1.0, 0.0),),
        indexed_at=datetime(2026, 1, 2, tzinfo=UTC),
        vector_index=vector_index,
        document_repository=repository,
        unit_of_work=FakeUnitOfWork(),
    )

    remove_document_index(
        document_id=document.id,
        vector_index=vector_index,
        document_repository=repository,
        unit_of_work=unit_of_work,
        chunk_ids=(chunk.id,),
    )

    assert vector_index.search((1.0, 0.0), limit=10) == ()
    assert repository.get_state(document.id) is None


def test_remove_document_index_is_idempotent_for_a_missing_document() -> None:
    vector_index = FakeVectorIndex()
    repository = FakeDocumentRepository()
    unit_of_work = FakeUnitOfWork()

    remove_document_index(
        document_id=DocumentId("missing-doc-000"),
        vector_index=vector_index,
        document_repository=repository,
        unit_of_work=unit_of_work,
    )

    assert unit_of_work.committed
