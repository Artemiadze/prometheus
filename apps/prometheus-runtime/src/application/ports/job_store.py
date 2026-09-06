"""Background-job persistence application port."""

from typing import Protocol

from application.dto.job import Job, JobId


class JobStore(Protocol):
    """Persist and retrieve background-job state."""

    def create(self) -> Job: ...

    def get(self, job_id: JobId) -> Job | None: ...

    def update(self, job: Job) -> None: ...

    def delete(self, job_id: JobId) -> None: ...
