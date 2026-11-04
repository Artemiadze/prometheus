"""Unit tests for the sqlite-vec dense vector adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.outbound.sqlite.database import MetadataDatabase
from adapters.outbound.sqlite.vector_index import SqliteVecVectorIndex
from application.dto.embedding import EmbeddingFingerprint
from application.dto.index_status import IndexStatus
from application.errors import IndexCorruptedError, VaultMismatchError
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document, compute_content_hash
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
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
        id=ChunkId.from_parts(document.id, ("Section",), 1, index),
        document_id=document.id,
        text=text,
        heading_path=("Section",),
        chunk_index=index,
        char_range=CharRange(index * 100, index * 100 + len(text)),
        token_count=max(1, len(text.split())),
        content_hash=compute_content_hash(text),
        heading_line=0,
        heading_occurrence=1,
    )


def _open_db(
    tmp_path: Path, *, dimension: int = 3
) -> tuple[MetadataDatabase, SqliteVecVectorIndex]:
    database = MetadataDatabase(tmp_path)
    index = database.vector_index(
        vault_id=VaultId("vault-01"),
        embedding_fingerprint=_fingerprint(dimension),
    )
    return database, index


def _index_document(
    database: MetadataDatabase,
    index: SqliteVecVectorIndex,
    document: Document,
    chunks: tuple[Chunk, ...],
    vectors: tuple[tuple[float, ...], ...],
) -> None:
    index.upsert(document, chunks, vectors)
    database.documents.save_indexed(document, chunks, datetime(2026, 1, 2, tzinfo=UTC))


def test_creates_vector_table_with_embedding_dimension(tmp_path: Path) -> None:
    database, index = _open_db(tmp_path)
    assert index.status is IndexStatus.READY
    row = database.connection.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'chunk_vectors'"
    ).fetchone()
    assert row is not None
    assert "float[3]" in row["sql"]
    database.close()


def test_persistent_collection_is_reused_after_restart(tmp_path: Path) -> None:
    document = _document("document-01", "Notes/One.md")
    chunk = _chunk(document, 0, "persistent chunk")
    first_db, first = _open_db(tmp_path)
    _index_document(first_db, first, document, (chunk,), ((1.0, 0.0, 0.0),))
    first_db.close()

    second_db, second = _open_db(tmp_path)
    assert second.status is IndexStatus.READY
    assert second.search((1.0, 0.0, 0.0), 10)[0].chunk == chunk
    second_db.close()


def test_search_reconstructs_domain_chunk_and_orders_scores(tmp_path: Path) -> None:
    database, index = _open_db(tmp_path)
    document = _document("document-01", "Notes/One.md")
    first = _chunk(document, 0, "closest")
    second = _chunk(document, 1, "orthogonal")
    _index_document(
        database,
        index,
        document,
        (first, second),
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    )

    hits = index.search((1.0, 0.0, 0.0), limit=2)

    assert [hit.chunk for hit in hits] == [first, second]
    assert hits[0].score == hits[0].dense_score == pytest.approx(1.0)
    assert hits[0].score >= hits[1].score
    database.close()


def test_save_indexed_stores_content_and_folder_ancestors(tmp_path: Path) -> None:
    database, index = _open_db(tmp_path)
    document = _document("document-01", "Work/Nested/One.md")
    chunk = _chunk(document, 0, "payload")
    _index_document(database, index, document, (chunk,), ((1.0, 0.0, 0.0),))

    content = database.connection.execute(
        "SELECT content FROM chunks WHERE chunk_id = ?", (chunk.id.value,)
    ).fetchone()
    ancestors = {
        row["folder"]
        for row in database.connection.execute(
            "SELECT folder FROM chunk_folder_ancestors WHERE chunk_id = ?",
            (chunk.id.value,),
        ).fetchall()
    }

    assert content["content"] == "payload"
    assert ancestors == {"Work/Nested", "Work"}
    database.close()


def test_delete_by_ids_removes_only_listed_chunks(tmp_path: Path) -> None:
    database, index = _open_db(tmp_path)
    document = _document("document-01", "Notes/One.md")
    first = _chunk(document, 0, "first")
    second = _chunk(document, 1, "second")
    _index_document(
        database,
        index,
        document,
        (first, second),
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    )

    index.delete_by_ids((first.id,))

    hits = index.search((0.0, 1.0, 0.0), 10)
    assert [hit.chunk for hit in hits] == [second]
    database.close()


def test_delete_by_document_removes_only_that_document(tmp_path: Path) -> None:
    database, index = _open_db(tmp_path)
    first_document = _document("document-01", "Notes/One.md")
    second_document = _document("document-02", "Notes/Two.md")
    _index_document(
        database,
        index,
        first_document,
        (_chunk(first_document, 0, "first"),),
        ((1.0, 0.0, 0.0),),
    )
    _index_document(
        database,
        index,
        second_document,
        (_chunk(second_document, 0, "second"),),
        ((1.0, 0.0, 0.0),),
    )

    index.delete_by_document(first_document.id)

    hits = index.search((1.0, 0.0, 0.0), 10)
    assert [hit.chunk.document_id for hit in hits] == [second_document.id]
    database.close()


def test_search_scope_filters_note_and_nested_folders(tmp_path: Path) -> None:
    database, index = _open_db(tmp_path)
    documents = (
        _document("document-01", "Work/Current.md"),
        _document("document-02", "Work/Nested/Child.md"),
        _document("document-03", "Personal/Private.md"),
    )
    for document in documents:
        _index_document(
            database,
            index,
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
    database.close()


def test_search_excludes_ignored_folder_ancestors(tmp_path: Path) -> None:
    database, index = _open_db(tmp_path)
    documents = (
        _document("document-01", "Archive/hidden.md"),
        _document("document-02", "Notes/visible.md"),
    )
    for document in documents:
        _index_document(
            database,
            index,
            document,
            (_chunk(document, 0, document.relative_path.value),),
            ((1.0, 0.0, 0.0),),
        )

    scope = SearchScope.entire_vault().with_exclusions(["Archive"])
    hits = index.search((1.0, 0.0, 0.0), 10, scope)

    assert {hit.chunk.document_id for hit in hits} == {documents[1].id}
    database.close()


def test_update_document_path_moves_scope_without_replacing_vectors(
    tmp_path: Path,
) -> None:
    database, index = _open_db(tmp_path)
    document = _document("document-01", "Work/Current.md")
    chunk = _chunk(document, 0, "unchanged vector")
    _index_document(database, index, document, (chunk,), ((1.0, 0.0, 0.0),))

    database.documents.update_path(document.id, RelativePath("Archive/Current.md"))
    index.update_document_path(document.id, RelativePath("Archive/Current.md"))

    assert index.search((1.0, 0.0, 0.0), 10, SearchScope.current_folder("Work")) == ()
    hits = index.search(
        (1.0, 0.0, 0.0),
        10,
        SearchScope.current_folder("Archive"),
    )
    assert [hit.chunk.id for hit in hits] == [chunk.id]
    database.close()


def test_incompatible_dimension_is_recreated_and_requests_reindex(tmp_path: Path) -> None:
    document = _document("document-01", "Notes/One.md")
    original_db, original = _open_db(tmp_path, dimension=3)
    _index_document(
        original_db,
        original,
        document,
        (_chunk(document, 0, "old"),),
        ((1.0, 0.0, 0.0),),
    )
    original_db.close()

    rebuilt_db, rebuilt = _open_db(tmp_path, dimension=2)

    assert rebuilt.status is IndexStatus.CORRUPTED
    with pytest.raises(IndexCorruptedError) as caught:
        rebuilt.search((1.0, 0.0), 10)
    assert caught.value.code == "INDEX_CORRUPTED"

    _index_document(
        rebuilt_db,
        rebuilt,
        document,
        (_chunk(document, 0, "new"),),
        ((1.0, 0.0),),
    )
    assert str(rebuilt.status) == IndexStatus.READY.value
    assert len(rebuilt.search((1.0, 0.0), 10)) == 1
    rebuilt_db.close()


def test_upsert_rejects_document_from_another_vault(tmp_path: Path) -> None:
    database, index = _open_db(tmp_path)
    foreign = Document.create(
        id=DocumentId("document-01"),
        vault_id=VaultId("vault-02"),
        relative_path="Notes/One.md",
        content="foreign",
        revision=1,
        modified_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    chunk = _chunk(foreign, 0, "foreign chunk")

    with pytest.raises(VaultMismatchError):
        index.upsert(foreign, (chunk,), ((1.0, 0.0, 0.0),))
    database.close()


def test_retrieve_vectors_returns_stored_embeddings(tmp_path: Path) -> None:
    database, index = _open_db(tmp_path)
    document = _document("document-01", "Notes/One.md")
    chunk = _chunk(document, 0, "vector")
    _index_document(database, index, document, (chunk,), ((1.0, 0.0, 0.0),))

    vectors = index.retrieve_vectors((chunk.id,))

    assert chunk.id.value in vectors
    assert vectors[chunk.id.value] == pytest.approx((1.0, 0.0, 0.0))
    database.close()


def test_input_validation_happens_before_existing_points_are_deleted(
    tmp_path: Path,
) -> None:
    database, index = _open_db(tmp_path)
    document = _document("document-01", "Notes/One.md")
    chunk = _chunk(document, 0, "preserved")
    _index_document(database, index, document, (chunk,), ((1.0, 0.0, 0.0),))

    with pytest.raises(ValueError, match="dimension"):
        index.upsert(document, (chunk,), ((1.0, 0.0),))

    assert index.search((1.0, 0.0, 0.0), 10)[0].chunk == chunk
    database.close()
