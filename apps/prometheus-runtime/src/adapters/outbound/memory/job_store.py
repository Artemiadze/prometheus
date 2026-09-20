"""Thread-safe process-local JobStore until PRM-E11 SQLite persistence."""

from __future__ import annotations

from threading import Lock

from application.dto.job import Job, JobId, JobStatus


class InMemoryJobStore:
    """Keep background job state for the lifetime of one runtime process."""

    def __init__(self) -> None:
        self._jobs: dict[JobId, Job] = {}
        self._lock = Lock()
        self._next_id = 1

    def create(self) -> Job:
        with self._lock:
            job = Job(JobId(f"job-{self._next_id:06d}"), JobStatus.PENDING, 0.0)
            self._next_id += 1
            self._jobs[job.id] = job
            return job

    def get(self, job_id: JobId) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def delete(self, job_id: JobId) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)
