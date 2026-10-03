"""Vault-scoped grounded chat routes."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from adapters.inbound.http.auth import require_session_token
from adapters.inbound.http.dependencies import get_vault_container
from adapters.inbound.http.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamDoneEvent,
    ChatStreamErrorEvent,
    ChatStreamSourcesEvent,
    ChatStreamTokenEvent,
    source_responses,
)
from adapters.inbound.http.schemas.common import ERROR_RESPONSES
from adapters.inbound.http.version_gate import require_compatible_plugin_version
from application.dto.answer_stream import AnswerCompletedEvent, AnswerTokenEvent
from domain.errors import PrometheusError

router = APIRouter(
    prefix="/v1/vaults/{vault_id}",
    dependencies=[Depends(require_session_token), Depends(require_compatible_plugin_version)],
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


@router.post(
    "/chat/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "NDJSON stream of chat events",
            "content": {
                "application/x-ndjson": {
                    "schema": {
                        "oneOf": [
                            {"$ref": "#/components/schemas/ChatStreamTokenEvent"},
                            {"$ref": "#/components/schemas/ChatStreamSourcesEvent"},
                            {"$ref": "#/components/schemas/ChatStreamDoneEvent"},
                            {"$ref": "#/components/schemas/ChatStreamErrorEvent"},
                        ]
                    }
                }
            },
        },
        **ERROR_RESPONSES,
    },
)
async def chat_stream(request: Request, vault_id: str, body: ChatRequest) -> StreamingResponse:
    scope = None if body.scope is None else body.scope.to_domain()
    answer_question = get_vault_container(request, vault_id).answer_question

    async def events() -> AsyncIterator[bytes]:
        try:
            async for event in answer_question.stream(body.query, scope=scope, limit=body.limit):
                if await request.is_disconnected():
                    break
                if isinstance(event, AnswerTokenEvent):
                    payload = ChatStreamTokenEvent(text=event.text).model_dump()
                elif isinstance(event, AnswerCompletedEvent):
                    payload = ChatStreamSourcesEvent(
                        sources=source_responses(event.sources),
                        insufficient_context=event.insufficient_context,
                    ).model_dump()
                    yield _encode(payload)
                    payload = ChatStreamDoneEvent().model_dump()
                else:
                    continue
                yield _encode(payload)
        except PrometheusError as error:
            yield _encode(
                ChatStreamErrorEvent(code=error.code, message=str(error)).model_dump(),
            )
        except Exception:
            yield _encode(
                ChatStreamErrorEvent(
                    code="INTERNAL_ERROR",
                    message="An internal runtime error occurred",
                ).model_dump(),
            )

    return StreamingResponse(events(), media_type="application/x-ndjson")


def _encode(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode()
