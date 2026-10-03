"""Semantic note search without invoking an LLM."""

from application.dto.search_result import SearchResult
from application.services.retrieval import RetrievalService
from domain.value_objects.search_scope import SearchScope


class SearchNotes:
    def __init__(self, retrieval: RetrievalService) -> None:
        self._retrieval = retrieval

    async def execute(
        self,
        query: str,
        *,
        scope: SearchScope | None = None,
        limit: int,
    ) -> tuple[SearchResult, ...]:
        retrieved = await self._retrieval.retrieve(query, scope=scope, limit=limit)
        return tuple(
            SearchResult(
                document_id=item.hit.chunk.document_id,
                chunk_id=item.hit.chunk.id,
                relative_path=item.relative_path,
                heading=item.hit.chunk.heading,
                text=item.hit.chunk.text,
                score=item.hit.score,
                heading_line=item.hit.chunk.heading_line,
                heading_occurrence=item.hit.chunk.heading_occurrence,
            )
            for item in retrieved
        )
