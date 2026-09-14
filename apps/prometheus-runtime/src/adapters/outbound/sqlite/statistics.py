"""SQLite-backed aggregate statistics for one Vault's index."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from adapters.outbound.sqlite.errors import wrap_driver_errors
from application.dto.statistics import IndexStatistics


class SqliteIndexStatisticsReader:
    """Serve manifest aggregates plus an on-disk size walk, never touching Qdrant."""

    def __init__(self, connection: sqlite3.Connection, vault_dir: Path) -> None:
        self._connection = connection
        self._vault_dir = vault_dir

    @wrap_driver_errors
    def read(self) -> IndexStatistics:
        document_count = self._connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunk_count = self._connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        last_indexed_at_raw = self._connection.execute(
            "SELECT MAX(indexed_at) FROM documents"
        ).fetchone()[0]
        last_indexed_at = (
            datetime.fromisoformat(last_indexed_at_raw) if last_indexed_at_raw else None
        )
        return IndexStatistics(
            document_count=document_count,
            chunk_count=chunk_count,
            last_indexed_at=last_indexed_at,
            index_size_bytes=_directory_size(self._vault_dir),
        )


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(entry.stat().st_size for entry in path.rglob("*") if entry.is_file())
