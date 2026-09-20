"""Vault reindex background-job route."""

from fastapi import APIRouter, Depends, Request, status

from adapters.inbound.http.auth import require_session_token
from adapters.inbound.http.dependencies import get_vault_container
from adapters.inbound.http.schemas.common import ERROR_RESPONSES
from adapters.inbound.http.schemas.reindex import ReindexRequest
from adapters.inbound.http.schemas.sync import JobStartedResponse
from adapters.inbound.http.version_gate import require_compatible_plugin_version
from domain.value_objects.vault_id import VaultId

router = APIRouter(
    prefix="/v1/vaults/{vault_id}",
    dependencies=[Depends(require_session_token), Depends(require_compatible_plugin_version)],
)


@router.post("/reindex", status_code=status.HTTP_202_ACCEPTED, responses=ERROR_RESPONSES)
async def reindex(
    request: Request,
    vault_id: str,
    body: ReindexRequest,
) -> JobStartedResponse:
    vault = VaultId(vault_id)
    job = request.app.state.job_runner.start_reindex(
        vault,
        get_vault_container(request, vault_id),
        body.to_domain(vault),
    )
    return JobStartedResponse(job_id=job.id.value, status_url=f"/v1/jobs/{job.id.value}")
