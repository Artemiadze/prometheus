"""HTTP schemas for grounded chat answers."""

from typing import Literal

from adapters.inbound.http.schemas.common import ApiSchema
from adapters.inbound.http.schemas.search import SearchScopeRequest
from domain.entities.grounded_answer import GroundedAnswer
from domain.value_objects.source_reference import SourceReference


class ChatRequest(ApiSchema):
    query: str
    limit: int = 10
    scope: SearchScopeRequest | None = None


class SourceResponse(ApiSchema):
    path: str
    heading: str | None
    link: str
    heading_line: int | None = None
    heading_occurrence: int | None = None


class ChatResponse(ApiSchema):
    answer: str
    sources: tuple[SourceResponse, ...]
    insufficient_context: bool

    @classmethod
    def from_domain(cls, answer: GroundedAnswer) -> "ChatResponse":
        return cls(
            answer=answer.text,
            sources=tuple(
                SourceResponse(
                    path=source.relative_path.value,
                    heading=source.heading,
                    link=source.link,
                    heading_line=source.heading_line,
                    heading_occurrence=source.heading_occurrence,
                )
                for source in answer.sources
            ),
            insufficient_context=answer.insufficient_context,
        )


class ChatStreamTokenEvent(ApiSchema):
    type: Literal["token"] = "token"
    text: str


class ChatStreamSourcesEvent(ApiSchema):
    type: Literal["sources"] = "sources"
    sources: tuple[SourceResponse, ...]
    insufficient_context: bool


class ChatStreamDoneEvent(ApiSchema):
    type: Literal["done"] = "done"


class ChatStreamHeartbeatEvent(ApiSchema):
    type: Literal["heartbeat"] = "heartbeat"


class ChatStreamErrorEvent(ApiSchema):
    type: Literal["error"] = "error"
    code: str
    message: str


def source_responses(sources: tuple[SourceReference, ...]) -> tuple[SourceResponse, ...]:
    return tuple(
        SourceResponse(
            path=source.relative_path.value,
            heading=source.heading,
            link=source.link,
            heading_line=source.heading_line,
            heading_occurrence=source.heading_occurrence,
        )
        for source in sources
    )
