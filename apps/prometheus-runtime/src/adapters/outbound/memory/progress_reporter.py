"""Process-local structured progress reporting until PRM-E11."""

from __future__ import annotations

from threading import Lock

from application.dto.indexing import IndexingProgress
from application.dto.job import JobId


class InMemoryProgressReporter:
    """Keep the most recent progress snapshot for each active job."""

    def __init__(self) -> None:
        self._progress: dict[JobId, IndexingProgress] = {}
        self._lock = Lock()

    def report(self, job_id: JobId, progress: IndexingProgress) -> None:
        with self._lock:
            self._progress[job_id] = progress

    def get(self, job_id: JobId) -> IndexingProgress | None:
        with self._lock:
            return self._progress.get(job_id)
