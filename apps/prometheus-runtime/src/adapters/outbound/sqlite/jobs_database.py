"""Global SQLite database for background job state."""

from __future__ import annotations

from pathlib import Path

from adapters.outbound.sqlite.connection import open_connection
from adapters.outbound.sqlite.job_progress import SqliteProgressReporter
from adapters.outbound.sqlite.job_store import SqliteJobStore
from adapters.outbound.sqlite.jobs_migrations import apply_jobs_migrations

JOBS_DATABASE_FILENAME = "jobs.sqlite"


class JobsDatabase:
    """Open ``state/jobs.sqlite``, migrate it, and expose job adapters."""

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = state_dir.expanduser().resolve()
        self.path = self._state_dir / JOBS_DATABASE_FILENAME
        self._connection = open_connection(self.path)
        apply_jobs_migrations(self._connection)
        self.job_store = SqliteJobStore(self._connection)
        self.progress_reporter = SqliteProgressReporter(self._connection)

    def close(self) -> None:
        self._connection.close()
