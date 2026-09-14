"""Tests for SQLite-backed index statistics (PRM-41)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from adapters.outbound.sqlite.database import MetadataDatabase
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId


def _document(identifier: str, path: str) -> Document:
    return Document.create(
        id=DocumentId(identifier),
        vault_id=VaultId("vault-01"),
        relative_path=path,
        content="Body",
        revision=1,
        modified_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_empty_index_reports_zero_counts(tmp_path: Path) -> None:
    database = MetadataDatabase(tmp_path)

    statistics = database.statistics.read()

    assert statistics.document_count == 0
    assert statistics.chunk_count == 0
    assert statistics.last_indexed_at is None
    database.close()


def test_statistics_reflect_saved_documents_and_last_indexed_at(tmp_path: Path) -> None:
    database = MetadataDatabase(tmp_path)
    first_indexed_at = datetime(2026, 1, 1, tzinfo=UTC)
    second_indexed_at = datetime(2026, 1, 2, tzinfo=UTC)
    database.documents.save_indexed(_document("document-01", "Notes/A.md"), (), first_indexed_at)
    database.documents.save_indexed(_document("document-02", "Notes/B.md"), (), second_indexed_at)

    statistics = database.statistics.read()

    assert statistics.document_count == 2
    assert statistics.last_indexed_at == second_indexed_at
    database.close()


def test_index_size_includes_the_qdrant_directory_without_querying_it(tmp_path: Path) -> None:
    database = MetadataDatabase(tmp_path)
    qdrant_dir = tmp_path / "qdrant"
    qdrant_dir.mkdir()
    (qdrant_dir / "storage.bin").write_bytes(b"x" * 128)

    statistics = database.statistics.read()

    assert statistics.index_size_bytes >= 128
    database.close()
