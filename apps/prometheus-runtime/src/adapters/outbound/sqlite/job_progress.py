"""SQLite-backed structured job progress reporting."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from adapters.outbound.sqlite.errors import wrap_driver_errors
from application.dto.indexing import IndexingProgress
from application.dto.job import JobId


class SqliteProgressReporter:
    """Persist indexing progress counters alongside the job row."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @wrap_driver_errors
    def report(self, job_id: JobId, progress: IndexingProgress) -> None:
        now = datetime.now(UTC).isoformat()
        self._connection.execute(
            """
            UPDATE jobs SET
                progress = ?,
                processed_documents = ?,
                total_documents = ?,
                processed_chunks = ?,
                updated_at = ?
            WHERE job_id = ?
            """,
            (
                progress.ratio,
                progress.processed_documents,
                progress.total_documents,
                progress.processed_chunks,
                now,
                job_id.value,
            ),
        )
