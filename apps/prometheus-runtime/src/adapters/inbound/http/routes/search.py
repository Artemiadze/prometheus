"""Vault-scoped semantic-search route."""

from fastapi import APIRouter, Depends, Request

from adapters.inbound.http.auth import require_session_token
from adapters.inbound.http.dependencies import get_vault_container
from adapters.inbound.http.schemas.common import ERROR_RESPONSES
from adapters.inbound.http.schemas.search import SearchRequest, SearchResponse, SearchResultResponse
from adapters.inbound.http.version_gate import require_compatible_plugin_version

router = APIRouter(
    prefix="/v1/vaults/{vault_id}",
    dependencies=[Depends(require_session_token), Depends(require_compatible_plugin_version)],
)


@router.post("/search", response_model=SearchResponse, responses=ERROR_RESPONSES)
async def search(request: Request, vault_id: str, body: SearchRequest) -> SearchResponse:
    scope = None if body.scope is None else body.scope.to_domain()
    results = await get_vault_container(request, vault_id).search_notes.execute(
        body.query,
        scope=scope,
        limit=body.limit,
    )
    return SearchResponse(
        results=tuple(SearchResultResponse.from_dto(result) for result in results)
    )
