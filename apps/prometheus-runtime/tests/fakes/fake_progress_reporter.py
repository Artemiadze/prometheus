"""In-memory ProgressReporter fake."""

from application.dto.job import JobId


class FakeProgressReporter:
    """Record every progress update in call order."""

    def __init__(self) -> None:
        self.updates: list[tuple[JobId, float]] = []

    def report(self, job_id: JobId, progress: float) -> None:
        self.updates.append((job_id, progress))
