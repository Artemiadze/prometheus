"""In-memory JobStore fake."""

from application.dto.job import Job, JobId, JobStatus


class FakeJobStore:
    """Persist job DTOs in memory with deterministic IDs."""

    def __init__(self) -> None:
        self.jobs: dict[JobId, Job] = {}
        self._next_id = 1

    def create(self) -> Job:
        job = Job(
            id=JobId(f"job-{self._next_id:06d}"),
            status=JobStatus.PENDING,
            progress=0.0,
        )
        self._next_id += 1
        self.jobs[job.id] = job
        return job

    def get(self, job_id: JobId) -> Job | None:
        return self.jobs.get(job_id)

    def update(self, job: Job) -> None:
        self.jobs[job.id] = job

    def delete(self, job_id: JobId) -> None:
        self.jobs.pop(job_id, None)
