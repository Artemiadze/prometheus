"""Tests for the SQLite-backed document manifest repository (PRM-38)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from adapters.outbound.sqlite.connection import open_connection
from adapters.outbound.sqlite.document_repository import SqliteDocumentRepository
from adapters.outbound.sqlite.migrations import apply_migrations
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document, compute_content_hash
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId


def _document(identifier: str = "document-01", path: str = "Notes/One.md") -> Document:
    return Document.create(
        id=DocumentId(identifier),
        vault_id=VaultId("vault-01"),
        relative_path=path,
        content="Body text",
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
        char_range=CharRange(index * 10, index * 10 + len(text)),
        token_count=max(1, len(text.split())),
        content_hash=compute_content_hash(text),
    )


def _repository(tmp_path: Path) -> SqliteDocumentRepository:
    connection = open_connection(tmp_path / "metadata.sqlite")
    apply_migrations(connection)
    return SqliteDocumentRepository(connection)


def test_save_indexed_returns_domain_types_from_get_state(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    document = _document()
    chunk = _chunk(document, 0, "first chunk")
    indexed_at = datetime(2026, 1, 2, tzinfo=UTC)

    repository.save_indexed(document, (chunk,), indexed_at)

    state = repository.get_state(document.id)
    assert state is not None
    assert state.document_id == document.id
    assert state.relative_path == document.relative_path
    assert state.content_hash == document.content_hash
    assert state.revision == document.revision
    assert state.indexed_at == indexed_at
    assert state.chunk_count == 1
    assert repository.get_state(DocumentId("missing-doc-000")) is None


def test_list_relative_paths_reflects_saved_documents(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    first = _document("document-01", "Notes/A.md")
    second = _document("document-02", "Notes/B.md")
    repository.save_indexed(second, (), datetime(2026, 1, 1, tzinfo=UTC))
    repository.save_indexed(first, (), datetime(2026, 1, 1, tzinfo=UTC))

    paths = repository.list_relative_paths()

    assert [path.value for path in paths] == ["Notes/A.md", "Notes/B.md"]


def test_list_states_orders_by_relative_path(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    second = _document("document-02", "Notes/B.md")
    first = _document("document-01", "Notes/A.md")
    repository.save_indexed(second, (), datetime(2026, 1, 1, tzinfo=UTC))
    repository.save_indexed(first, (), datetime(2026, 1, 1, tzinfo=UTC))

    states = repository.list_states()

    assert [state.relative_path.value for state in states] == ["Notes/A.md", "Notes/B.md"]


def test_reindexing_replaces_chunk_rows_without_duplicates(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    document = _document()
    old_chunks = (_chunk(document, 0, "old-a"), _chunk(document, 1, "old-b"))
    repository.save_indexed(document, old_chunks, datetime(2026, 1, 1, tzinfo=UTC))

    new_chunk = _chunk(document, 0, "new")
    repository.save_indexed(document, (new_chunk,), datetime(2026, 1, 2, tzinfo=UTC))

    state = repository.get_state(document.id)
    assert state is not None
    assert state.chunk_count == 1


def test_delete_cascades_chunks_and_is_idempotent(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    document = _document()
    repository.save_indexed(
        document, (_chunk(document, 0, "chunk"),), datetime(2026, 1, 1, tzinfo=UTC)
    )

    repository.delete(document.id)
    repository.delete(document.id)

    assert repository.get_state(document.id) is None
    assert repository.list_relative_paths() == ()
