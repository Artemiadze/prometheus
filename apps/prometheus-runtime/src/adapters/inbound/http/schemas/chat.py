"""HTTP schemas for grounded chat answers."""

from adapters.inbound.http.schemas.common import ApiSchema
from adapters.inbound.http.schemas.search import SearchScopeRequest
from domain.entities.grounded_answer import GroundedAnswer


class ChatRequest(ApiSchema):
    query: str
    limit: int = 10
    scope: SearchScopeRequest | None = None


class SourceResponse(ApiSchema):
    path: str
    heading: str | None


class ChatResponse(ApiSchema):
    answer: str
    sources: tuple[SourceResponse, ...]
    insufficient_context: bool

    @classmethod
    def from_domain(cls, answer: GroundedAnswer) -> "ChatResponse":
        return cls(
            answer=answer.text,
            sources=tuple(
                SourceResponse(path=source.relative_path.value, heading=source.heading)
                for source in answer.sources
            ),
            insufficient_context=answer.insufficient_context,
        )
