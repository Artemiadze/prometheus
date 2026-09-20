"""Global background-job inspection and cancellation routes."""

from fastapi import APIRouter, Depends, Request, Response, status

from adapters.inbound.http.auth import require_session_token
from adapters.inbound.http.schemas.common import ERROR_RESPONSES
from adapters.inbound.http.schemas.jobs import JobResponse
from adapters.inbound.http.version_gate import require_compatible_plugin_version
from application.dto.job import JobId
from application.errors import JobNotFoundError

router = APIRouter(
    prefix="/v1/jobs",
    dependencies=[Depends(require_session_token), Depends(require_compatible_plugin_version)],
)


@router.get("/{job_id}", response_model=JobResponse, responses=ERROR_RESPONSES)
async def get_job(request: Request, job_id: str) -> JobResponse:
    job = request.app.state.job_store.get(JobId(job_id))
    if job is None:
        raise JobNotFoundError()
    return JobResponse.from_dto(job)


@router.delete("/{job_id}", status_code=status.HTTP_202_ACCEPTED, responses=ERROR_RESPONSES)
async def cancel_job(request: Request, job_id: str) -> Response:
    if not request.app.state.job_runner.cancel(JobId(job_id)):
        raise JobNotFoundError()
    return Response(status_code=status.HTTP_202_ACCEPTED)
