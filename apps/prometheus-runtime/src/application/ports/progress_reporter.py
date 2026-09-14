"""Background-job progress reporting application port."""

from typing import Protocol

from application.dto.indexing import IndexingProgress
from application.dto.job import JobId


class ProgressReporter(Protocol):
    """Report structured progress for an application job."""

    def report(self, job_id: JobId, progress: IndexingProgress) -> None: ...
