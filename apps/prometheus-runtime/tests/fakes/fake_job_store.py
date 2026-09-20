"""In-memory JobStore fake."""

from datetime import UTC, datetime

from application.dto.job import Job, JobId, JobKind, JobStatus
from domain.value_objects.vault_id import VaultId

_INTERRUPTED = "JOB_INTERRUPTED"


class FakeJobStore:
    """Persist job DTOs in memory with deterministic IDs."""

    def __init__(self) -> None:
        self.jobs: dict[JobId, Job] = {}
        self._next_id = 1

    def create(self, vault_id: VaultId, kind: JobKind) -> Job:
        now = datetime.now(UTC)
        job = Job(
            id=JobId(f"job-{self._next_id:06d}"),
            vault_id=vault_id,
            kind=kind,
            status=JobStatus.PENDING,
            progress=0.0,
            processed_documents=0,
            total_documents=0,
            processed_chunks=0,
            created_at=now,
            updated_at=now,
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

    def find_active(self, vault_id: VaultId) -> Job | None:
        for job in self.jobs.values():
            if job.vault_id == vault_id and job.status in {
                JobStatus.PENDING,
                JobStatus.RUNNING,
            }:
                return job
        return None

    def recover_interrupted(self) -> int:
        count = 0
        for job_id, job in list(self.jobs.items()):
            if job.status in {JobStatus.PENDING, JobStatus.RUNNING}:
                self.jobs[job_id] = job.with_state(
                    status=JobStatus.FAILED,
                    progress=job.progress,
                    processed_documents=job.processed_documents,
                    total_documents=job.total_documents,
                    processed_chunks=job.processed_chunks,
                    updated_at=datetime.now(UTC),
                    error=_INTERRUPTED,
                )
                count += 1
        return count
