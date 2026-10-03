"""SQLite schema upgrade v1 → v2 without losing indexed documents (PRM-84)."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from adapters.outbound.sqlite.connection import open_connection
from adapters.outbound.sqlite.migrations import MIGRATIONS, apply_migrations
from application.dto.embedding import EmbeddingFingerprint
from application.dto.index_fingerprint import IndexFingerprint
from application.dto.runtime_status import IndexState
from application.dto.statistics import IndexStatistics
from application.errors import IndexRebuildRequiredError
from application.services.index_fingerprint import ensure_index_compatible
from application.services.retrieval import RetrievalService
from application.use_cases.get_runtime_status import GetRuntimeStatus
from application.use_cases.search_notes import SearchNotes
from fakes import (
    FakeDocumentRepository,
    FakeEmbedder,
    FakeIndexMetadataStore,
    FakeIndexStatisticsReader,
    FakeLanguageModel,
    FakeVectorIndex,
)

pytestmark = pytest.mark.integration


def _tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows}


def test_upgrade_from_schema_v1_preserves_documents_and_chunks(tmp_path: Path) -> None:
    path = tmp_path / "metadata.sqlite"
    connection = open_connection(path)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    version_one = next(statements for version, statements in MIGRATIONS if version == 1)
    connection.execute("BEGIN")
    for statement in version_one:
        connection.execute(statement)
    connection.execute(
        "INSERT INTO schema_version (version, applied_at) VALUES (1, ?)",
        ("2026-01-01T00:00:00+00:00",),
    )
    connection.execute("COMMIT")

    connection.execute("BEGIN")
    connection.execute(
        """
        INSERT INTO documents (
            document_id, relative_path, revision, content_hash, modified_at, indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "document-01",
            "Notes/One.md",
            1,
            "a" * 64,
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    connection.execute(
        """
        INSERT INTO chunks (
            chunk_id, document_id, chunk_index, heading_path,
            char_start, char_end, token_count, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("chunk-01", "document-01", 0, '["Section"]', 0, 10, 2, "b" * 64),
    )
    connection.execute(
        """
        INSERT INTO jobs (job_id, status, progress, error, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("job-01", "running", 0.5, None, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
    )
    connection.execute("COMMIT")

    apply_migrations(connection)

    versions = [
        row[0] for row in connection.execute("SELECT version FROM schema_version ORDER BY version")
    ]
    assert versions == [1, 2, 3, 4, 5]
    assert "jobs" not in _tables(connection)
    assert "chunks_fts" in _tables(connection)
    document = connection.execute("SELECT document_id, relative_path FROM documents").fetchone()
    chunk = connection.execute("SELECT chunk_id, document_id FROM chunks").fetchone()
    assert document is not None and tuple(document) == ("document-01", "Notes/One.md")
    assert chunk is not None and tuple(chunk) == ("chunk-01", "document-01")
    connection.close()


def test_embedding_model_change_marks_index_rebuild_required() -> None:
    embedder = FakeEmbedder()
    stored = IndexFingerprint(
        EmbeddingFingerprint("fastembed", "old/model", embedder.fingerprint.dimension),
        parser_version=1,
        chunker_version=1,
        payload_schema_version=1,
        chunk_size=700,
        chunk_overlap=80,
    )
    active = IndexFingerprint(
        EmbeddingFingerprint("fastembed", "new/model", embedder.fingerprint.dimension),
        parser_version=1,
        chunker_version=1,
        payload_schema_version=1,
        chunk_size=700,
        chunk_overlap=80,
    )
    with pytest.raises(IndexRebuildRequiredError, match="embedding"):
        ensure_index_compatible(stored, active)

    metadata = FakeIndexMetadataStore(stored)
    documents = FakeDocumentRepository()
    vectors = FakeVectorIndex()
    retrieval = RetrievalService(
        embedder=embedder,
        vector_index=vectors,
        document_repository=documents,
        index_metadata_store=metadata,
        active_fingerprint=active,
    )
    status = GetRuntimeStatus(
        runtime_version="0.1.0",
        llm_model="qwen3:4b",
        language_model=FakeLanguageModel(),
        vector_index=vectors,
        index_metadata_store=metadata,
        index_statistics=FakeIndexStatisticsReader(
            IndexStatistics(
                document_count=1, chunk_count=1, last_indexed_at=None, index_size_bytes=10
            )
        ),
        active_fingerprint=active,
    )

    report = asyncio.run(status.execute())
    assert report.index_state is IndexState.REBUILD_REQUIRED
    assert report.reindex_required is True

    with pytest.raises(IndexRebuildRequiredError):
        asyncio.run(SearchNotes(retrieval).execute("query text", limit=5))
