"""Vault-scoped grounded chat route."""

from fastapi import APIRouter, Depends, Request

from adapters.inbound.http.auth import require_session_token
from adapters.inbound.http.dependencies import get_vault_container
from adapters.inbound.http.schemas.chat import ChatRequest, ChatResponse
from adapters.inbound.http.schemas.common import ERROR_RESPONSES

router = APIRouter(
    prefix="/v1/vaults/{vault_id}",
    dependencies=[Depends(require_session_token)],
)


@router.post("/chat", response_model=ChatResponse, responses=ERROR_RESPONSES)
async def chat(request: Request, vault_id: str, body: ChatRequest) -> ChatResponse:
    scope = None if body.scope is None else body.scope.to_domain()
    answer = await get_vault_container(request, vault_id).answer_question.execute(
        body.query,
        scope=scope,
        limit=body.limit,
    )
    return ChatResponse.from_domain(answer)
