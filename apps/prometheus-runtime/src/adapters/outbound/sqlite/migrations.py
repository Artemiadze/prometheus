"""Ordered, idempotent SQLite schema migrations for the metadata database."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from adapters.outbound.sqlite.errors import SchemaDowngradeError

_MIGRATION_1 = (
    """
    CREATE TABLE documents (
        document_id TEXT PRIMARY KEY,
        relative_path TEXT NOT NULL UNIQUE,
        revision INTEGER NOT NULL,
        content_hash TEXT NOT NULL,
        modified_at TEXT NOT NULL,
        indexed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE chunks (
        chunk_id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL REFERENCES documents (document_id) ON DELETE CASCADE,
        chunk_index INTEGER NOT NULL,
        heading_path TEXT NOT NULL,
        char_start INTEGER NOT NULL,
        char_end INTEGER NOT NULL,
        token_count INTEGER NOT NULL,
        content_hash TEXT NOT NULL,
        UNIQUE (document_id, chunk_index)
    )
    """,
    "CREATE INDEX chunks_document_id_idx ON chunks (document_id)",
    """
    CREATE TABLE jobs (
        job_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        progress REAL NOT NULL,
        error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE index_meta (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        embedding_provider TEXT NOT NULL,
        embedding_model_id TEXT NOT NULL,
        embedding_dimension INTEGER NOT NULL,
        parser_version INTEGER NOT NULL,
        chunker_version INTEGER NOT NULL,
        payload_schema_version INTEGER NOT NULL,
        chunk_size INTEGER NOT NULL,
        chunk_overlap INTEGER NOT NULL
    )
    """,
)

#: Ordered (version, statements) pairs; each is applied inside its own transaction.
MIGRATIONS: tuple[tuple[int, tuple[str, ...]], ...] = ((1, _MIGRATION_1),)

LATEST_VERSION = MIGRATIONS[-1][0]

_SCHEMA_VERSION_TABLE = """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )
"""


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Bring the schema up to :data:`LATEST_VERSION`; re-running is a no-op.

    Raises :class:`SchemaDowngradeError` when the stored version is newer than this
    runtime knows about, so an older build never silently corrupts a newer schema.
    """

    connection.execute(_SCHEMA_VERSION_TABLE)
    current_version = _current_version(connection)
    if current_version > LATEST_VERSION:
        raise SchemaDowngradeError(current_version, LATEST_VERSION)

    for version, statements in MIGRATIONS:
        if version <= current_version:
            continue
        connection.execute("BEGIN")
        try:
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(UTC).isoformat()),
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise


def _current_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()
    value = row[0] if row is not None else None
    return int(value) if value is not None else 0
