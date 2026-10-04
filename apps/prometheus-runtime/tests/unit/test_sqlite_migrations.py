"""Tests for versioned, idempotent SQLite migrations (PRM-37)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from adapters.outbound.sqlite.connection import open_connection
from adapters.outbound.sqlite.errors import SchemaDowngradeError
from adapters.outbound.sqlite.migrations import LATEST_VERSION, apply_migrations


def _tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def test_migrations_create_expected_tables_and_enable_wal(tmp_path: Path) -> None:
    connection = open_connection(tmp_path / "metadata.sqlite")
    apply_migrations(connection)

    assert {"documents", "chunks", "index_meta", "schema_version"} <= _tables(
        connection
    )
    assert "chunks_fts" in _tables(connection)
    assert "jobs" not in _tables(connection)
    mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    assert foreign_keys == 1
    connection.close()


def test_migrations_are_idempotent(tmp_path: Path) -> None:
    connection = open_connection(tmp_path / "metadata.sqlite")
    apply_migrations(connection)
    apply_migrations(connection)

    rows = connection.execute("SELECT version FROM schema_version").fetchall()
    assert [row[0] for row in rows] == list(range(1, LATEST_VERSION + 1))
    connection.close()


def test_stored_version_newer_than_supported_is_rejected(tmp_path: Path) -> None:
    connection = open_connection(tmp_path / "metadata.sqlite")
    apply_migrations(connection)
    connection.execute(
        "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
        (LATEST_VERSION + 1, "2026-01-01T00:00:00+00:00"),
    )

    with pytest.raises(SchemaDowngradeError) as caught:
        apply_migrations(connection)

    assert caught.value.code == "SCHEMA_DOWNGRADE_UNSUPPORTED"
    connection.close()


def test_database_file_is_private_outside_the_vault_tree(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vaults" / "vault-01"
    path = vault_dir / "metadata.sqlite"
    connection = open_connection(path)
    apply_migrations(connection)
    connection.close()

    assert path.exists()
    assert path.stat().st_mode & 0o777 == 0o600


def test_deleting_a_document_cascades_its_chunks(tmp_path: Path) -> None:
    connection = open_connection(tmp_path / "metadata.sqlite")
    apply_migrations(connection)

    connection.execute("BEGIN")
    connection.execute(
        """
        INSERT INTO documents (
            document_id, relative_path, revision, content_hash, modified_at, indexed_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
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
        ("chunk-01", "document-01", 0, "[]", 0, 10, 2, "b" * 64),
    )
    connection.execute("COMMIT")

    connection.execute("BEGIN")
    connection.execute("DELETE FROM documents WHERE document_id = ?", ("document-01",))
    connection.execute("COMMIT")

    remaining = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    assert remaining == 0
    connection.close()
