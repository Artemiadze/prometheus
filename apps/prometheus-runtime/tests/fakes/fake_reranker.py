"""No-op Reranker fake."""

from collections.abc import Sequence

from domain.entities.search_hit import SearchHit


class FakeReranker:
    """Preserve retrieval order while recording the last query."""

    def __init__(self) -> None:
        self.last_query: str | None = None

    def rerank(self, query: str, hits: Sequence[SearchHit]) -> Sequence[SearchHit]:
        self.last_query = query
        return tuple(hits)
