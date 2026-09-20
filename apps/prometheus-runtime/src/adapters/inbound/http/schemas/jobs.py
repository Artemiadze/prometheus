"""HTTP schemas for background job state."""

from adapters.inbound.http.schemas.common import ApiSchema
from application.dto.job import Job


class JobResponse(ApiSchema):
    job_id: str
    status: str
    progress: float
    error: str | None

    @classmethod
    def from_dto(cls, job: Job) -> "JobResponse":
        return cls(
            job_id=job.id.value,
            status=job.status.value,
            progress=job.progress,
            error=job.error,
        )
