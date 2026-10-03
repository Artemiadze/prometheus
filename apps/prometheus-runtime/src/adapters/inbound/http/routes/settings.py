"""Vault settings routes."""

from fastapi import APIRouter, Depends, Request

from adapters.inbound.http.auth import require_session_token
from adapters.inbound.http.dependencies import get_vault_container
from adapters.inbound.http.schemas.common import ERROR_RESPONSES
from adapters.inbound.http.schemas.settings import IgnoredFoldersRequest, IgnoredFoldersResponse
from adapters.inbound.http.version_gate import require_compatible_plugin_version

router = APIRouter(
    prefix="/v1/vaults/{vault_id}/settings",
    dependencies=[Depends(require_session_token), Depends(require_compatible_plugin_version)],
)


@router.get("/ignored-folders", response_model=IgnoredFoldersResponse, responses=ERROR_RESPONSES)
async def get_ignored_folders(request: Request, vault_id: str) -> IgnoredFoldersResponse:
    ignored = get_vault_container(request, vault_id).vault_settings_store.load_ignored_folders()
    return IgnoredFoldersResponse.from_ignored(ignored)


@router.put("/ignored-folders", response_model=IgnoredFoldersResponse, responses=ERROR_RESPONSES)
async def put_ignored_folders(
    request: Request,
    vault_id: str,
    body: IgnoredFoldersRequest,
) -> IgnoredFoldersResponse:
    result = await get_vault_container(request, vault_id).update_ignored_folders.execute(
        body.folders,
    )
    return IgnoredFoldersResponse.from_update(result)
