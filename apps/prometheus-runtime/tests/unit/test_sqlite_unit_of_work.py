"""Tests for the SQLite transaction boundary (PRM-39)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from adapters.outbound.sqlite.connection import open_connection
from adapters.outbound.sqlite.migrations import apply_migrations
from adapters.outbound.sqlite.unit_of_work import SqliteUnitOfWork

_INSERT_DOCUMENT = """
    INSERT INTO documents (
        document_id, relative_path, revision, content_hash, modified_at, indexed_at
    )
    VALUES (?, ?, 1, ?, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
"""


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = open_connection(tmp_path / "metadata.sqlite")
    apply_migrations(connection)
    return connection


def test_commit_persists_writes(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    unit_of_work = SqliteUnitOfWork(connection)

    with unit_of_work:
        connection.execute(_INSERT_DOCUMENT, ("document-01", "Notes/One.md", "a" * 64))
        unit_of_work.commit()

    count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    assert count == 1
    connection.close()


def test_exception_inside_the_block_rolls_back(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    unit_of_work = SqliteUnitOfWork(connection)

    with pytest.raises(RuntimeError), unit_of_work:
        connection.execute(_INSERT_DOCUMENT, ("document-01", "Notes/One.md", "a" * 64))
        raise RuntimeError("boom")

    count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    assert count == 0
    connection.close()


def test_exit_without_commit_rolls_back(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    unit_of_work = SqliteUnitOfWork(connection)

    with unit_of_work:
        connection.execute(_INSERT_DOCUMENT, ("document-01", "Notes/One.md", "a" * 64))

    count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    assert count == 0
    connection.close()


def test_unit_of_work_is_reusable_across_transactions(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    unit_of_work = SqliteUnitOfWork(connection)

    with unit_of_work:
        connection.execute(_INSERT_DOCUMENT, ("document-01", "Notes/One.md", "a" * 64))
        unit_of_work.commit()

    with unit_of_work:
        connection.execute(_INSERT_DOCUMENT, ("document-02", "Notes/Two.md", "b" * 64))
        unit_of_work.commit()

    count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    assert count == 2
    connection.close()
