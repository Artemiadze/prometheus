"""Authenticated runtime status and local-model routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from adapters.inbound.http.auth import require_session_token
from adapters.inbound.http.dependencies import get_base_container, get_vault_container
from adapters.inbound.http.schemas.status import ModelResponse, ModelsResponse, StatusResponse
from adapters.inbound.http.version_gate import require_compatible_plugin_version
from application.services.version_compatibility import API_VERSION

router = APIRouter(
    dependencies=[Depends(require_session_token), Depends(require_compatible_plugin_version)]
)


@router.get("/v1/status", response_model=StatusResponse)
async def status(
    request: Request,
    vault_id: Annotated[str, Query(alias="vaultId")],
) -> StatusResponse:
    """Return status for the isolated Vault supplied as ``vault_id``."""

    result = await get_vault_container(request, vault_id).runtime_status.execute()
    return StatusResponse.from_dto(result, API_VERSION)


@router.get("/v1/models", response_model=ModelsResponse)
async def models(request: Request) -> ModelsResponse:
    """List locally installed Ollama models."""

    container = get_base_container(request)
    listed = await container.language_model.list_models()
    return ModelsResponse(models=tuple(ModelResponse.from_dto(model) for model in listed))
