"""Schema migrations for the global jobs SQLite database."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from adapters.outbound.sqlite.errors import SchemaDowngradeError

_MIGRATION_1 = (
    """
    CREATE TABLE jobs (
        job_id TEXT PRIMARY KEY,
        vault_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        status TEXT NOT NULL,
        progress REAL NOT NULL,
        processed_documents INTEGER NOT NULL DEFAULT 0,
        total_documents INTEGER NOT NULL DEFAULT 0,
        processed_chunks INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX jobs_active_per_vault_idx
        ON jobs (vault_id)
        WHERE status IN ('pending', 'running')
    """,
)

MIGRATIONS: tuple[tuple[int, tuple[str, ...]], ...] = ((1, _MIGRATION_1),)

LATEST_VERSION = MIGRATIONS[-1][0]

_SCHEMA_VERSION_TABLE = """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )
"""


def apply_jobs_migrations(connection: sqlite3.Connection) -> None:
    """Apply pending jobs-database migrations idempotently."""

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
