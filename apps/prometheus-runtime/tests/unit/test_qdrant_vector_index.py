"""Integration-style unit tests for the embedded Qdrant adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from qdrant_client import QdrantClient, models

from adapters.outbound.qdrant.adapter import COLLECTION_NAME, QdrantLocalVectorIndex
from application.dto.embedding import EmbeddingFingerprint
from application.dto.index_status import IndexStatus
from application.errors import IndexCorruptedError
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document, compute_content_hash
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.search_scope import SearchScope
from domain.value_objects.vault_id import VaultId


def _fingerprint(dimension: int = 3) -> EmbeddingFingerprint:
    return EmbeddingFingerprint("fastembed", "test/model", dimension)


def _document(identifier: str, path: str) -> Document:
    return Document.create(
        id=DocumentId(identifier),
        vault_id=VaultId("vault-01"),
        relative_path=path,
        content=f"Source for {path}",
        revision=1,
        modified_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _chunk(document: Document, index: int, text: str) -> Chunk:
    return Chunk(
        id=ChunkId.from_parts(document.id, ("Section",), index),
        document_id=document.id,
        text=text,
        heading_path=("Section",),
        chunk_index=index,
        char_range=CharRange(index * 100, index * 100 + len(text)),
        token_count=max(1, len(text.split())),
        content_hash=compute_content_hash(text),
    )


def _memory_index(
    tmp_path: Path,
    *,
    dimension: int = 3,
) -> tuple[QdrantLocalVectorIndex, QdrantClient]:
    client = QdrantClient(":memory:")
    index = QdrantLocalVectorIndex(
        vault_dir=tmp_path,
        embedding_fingerprint=_fingerprint(dimension),
        client_factory=lambda: client,
    )
    return index, client


def test_creates_cosine_collection_with_embedding_dimension(tmp_path: Path) -> None:
    index, client = _memory_index(tmp_path)

    vectors = client.get_collection(COLLECTION_NAME).config.params.vectors

    assert isinstance(vectors, models.VectorParams)
    assert vectors.size == 3
    assert vectors.distance is models.Distance.COSINE
    assert index.status is IndexStatus.READY


def test_persistent_collection_is_reused_after_restart(tmp_path: Path) -> None:
    document = _document("document-01", "Notes/One.md")
    chunk = _chunk(document, 0, "persistent chunk")
    first = QdrantLocalVectorIndex(
        vault_dir=tmp_path,
        embedding_fingerprint=_fingerprint(),
    )
    first.upsert(document, (chunk,), ((1.0, 0.0, 0.0),))
    first.close()

    second = QdrantLocalVectorIndex(
        vault_dir=tmp_path,
        embedding_fingerprint=_fingerprint(),
    )

    assert second.status is IndexStatus.READY
    assert second.search((1.0, 0.0, 0.0), 10)[0].chunk == chunk
    second.close()


def test_search_reconstructs_domain_chunk_and_orders_scores(tmp_path: Path) -> None:
    index, _ = _memory_index(tmp_path)
    document = _document("document-01", "Notes/One.md")
    first = _chunk(document, 0, "closest")
    second = _chunk(document, 1, "orthogonal")
    index.upsert(
        document,
        (first, second),
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    )

    hits = index.search((1.0, 0.0, 0.0), limit=2)

    assert [hit.chunk for hit in hits] == [first, second]
    assert hits[0].score == hits[0].dense_score == pytest.approx(1.0)
    assert hits[0].score >= hits[1].score


def test_point_payload_contains_versioned_search_schema(tmp_path: Path) -> None:
    index, client = _memory_index(tmp_path)
    document = _document("document-01", "Work/Nested/One.md")
    chunk = _chunk(document, 0, "payload")
    index.upsert(document, (chunk,), ((1.0, 0.0, 0.0),))

    records, _ = client.scroll(COLLECTION_NAME, limit=1, with_payload=True)
    payload = records[0].payload

    assert payload is not None
    assert payload["document_id"] == document.id.value
    assert payload["file_path"] == "Work/Nested/One.md"
    assert payload["folder"] == "Work/Nested"
    assert payload["folder_ancestors"] == ["Work/Nested", "Work"]
    assert payload["heading"] == "Section"
    assert payload["chunk_index"] == 0
    assert payload["content"] == "payload"
    assert payload["content_hash"] == chunk.content_hash
    assert payload["modified_at"] == document.modified_at.isoformat()


def test_reindex_replaces_all_old_document_chunks(tmp_path: Path) -> None:
    index, _ = _memory_index(tmp_path)
    document = _document("document-01", "Notes/One.md")
    old_first = _chunk(document, 0, "old first")
    old_second = _chunk(document, 1, "old second")
    replacement = _chunk(document, 0, "replacement")
    index.upsert(
        document,
        (old_first, old_second),
        ((1.0, 0.0, 0.0), (0.9, 0.1, 0.0)),
    )

    index.upsert(document, (replacement,), ((0.0, 1.0, 0.0),))

    assert [hit.chunk for hit in index.search((1.0, 0.0, 0.0), 10)] == [replacement]


def test_delete_by_document_removes_only_that_document(tmp_path: Path) -> None:
    index, _ = _memory_index(tmp_path)
    first_document = _document("document-01", "Notes/One.md")
    second_document = _document("document-02", "Notes/Two.md")
    index.upsert(
        first_document,
        (_chunk(first_document, 0, "first"),),
        ((1.0, 0.0, 0.0),),
    )
    index.upsert(
        second_document,
        (_chunk(second_document, 0, "second"),),
        ((1.0, 0.0, 0.0),),
    )

    index.delete_by_document(first_document.id)

    hits = index.search((1.0, 0.0, 0.0), 10)
    assert [hit.chunk.document_id for hit in hits] == [second_document.id]


def test_search_scope_filters_note_and_nested_folders(tmp_path: Path) -> None:
    index, _ = _memory_index(tmp_path)
    documents = (
        _document("document-01", "Work/Current.md"),
        _document("document-02", "Work/Nested/Child.md"),
        _document("document-03", "Personal/Private.md"),
    )
    for document in documents:
        index.upsert(
            document,
            (_chunk(document, 0, document.relative_path.value),),
            ((1.0, 0.0, 0.0),),
        )

    note_hits = index.search(
        (1.0, 0.0, 0.0),
        10,
        SearchScope.current_note("Work/Current.md"),
    )
    folder_hits = index.search(
        (1.0, 0.0, 0.0),
        10,
        SearchScope.current_folder("Work"),
    )
    selected_hits = index.search(
        (1.0, 0.0, 0.0),
        10,
        SearchScope.selected_folders(("Work/Nested", "Personal")),
    )

    assert {hit.chunk.document_id for hit in note_hits} == {documents[0].id}
    assert {hit.chunk.document_id for hit in folder_hits} == {
        documents[0].id,
        documents[1].id,
    }
    assert {hit.chunk.document_id for hit in selected_hits} == {
        documents[1].id,
        documents[2].id,
    }


def test_incompatible_index_is_recreated_and_requests_reindex(tmp_path: Path) -> None:
    document = _document("document-01", "Notes/One.md")
    original = QdrantLocalVectorIndex(
        vault_dir=tmp_path,
        embedding_fingerprint=_fingerprint(3),
    )
    original.upsert(document, (_chunk(document, 0, "old"),), ((1.0, 0.0, 0.0),))
    original.close()

    rebuilt = QdrantLocalVectorIndex(
        vault_dir=tmp_path,
        embedding_fingerprint=_fingerprint(2),
    )

    assert rebuilt.status is IndexStatus.CORRUPTED
    with pytest.raises(IndexCorruptedError) as caught:
        rebuilt.search((1.0, 0.0), 10)
    assert caught.value.code == "INDEX_CORRUPTED"

    rebuilt.upsert(document, (_chunk(document, 0, "new"),), ((1.0, 0.0),))
    assert str(rebuilt.status) == IndexStatus.READY.value
    assert len(rebuilt.search((1.0, 0.0), 10)) == 1
    rebuilt.close()


def test_corrupted_metadata_does_not_crash_startup(tmp_path: Path) -> None:
    original = QdrantLocalVectorIndex(
        vault_dir=tmp_path,
        embedding_fingerprint=_fingerprint(),
    )
    original.close()
    (tmp_path / "qdrant_metadata.json").write_text("{broken", encoding="utf-8")

    recovered = QdrantLocalVectorIndex(
        vault_dir=tmp_path,
        embedding_fingerprint=_fingerprint(),
    )

    assert recovered.status is IndexStatus.CORRUPTED
    with pytest.raises(IndexCorruptedError):
        recovered.search((1.0, 0.0, 0.0), 10)
    recovered.close()


def test_input_validation_happens_before_existing_points_are_deleted(tmp_path: Path) -> None:
    index, _ = _memory_index(tmp_path)
    document = _document("document-01", "Notes/One.md")
    chunk = _chunk(document, 0, "preserved")
    index.upsert(document, (chunk,), ((1.0, 0.0, 0.0),))

    with pytest.raises(ValueError, match="dimension"):
        index.upsert(document, (chunk,), ((1.0, 0.0),))

    assert index.search((1.0, 0.0, 0.0), 10)[0].chunk == chunk
