"""In-memory ProgressReporter fake."""

from application.dto.indexing import IndexingProgress
from application.dto.job import JobId


class FakeProgressReporter:
    """Record every progress update in call order."""

    def __init__(self) -> None:
        self.updates: list[tuple[JobId, IndexingProgress]] = []

    def report(self, job_id: JobId, progress: IndexingProgress) -> None:
        self.updates.append((job_id, progress))
