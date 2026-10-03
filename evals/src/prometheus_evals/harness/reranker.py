"""Deterministic local reranker for offline evaluation benchmarks."""

from __future__ import annotations

from collections.abc import Sequence

from domain.entities.search_hit import SearchHit, sort_by_score


class EvalDeterministicReranker:
    """Score chunks by token overlap with the query without loading a model."""

    def rerank(self, query: str, hits: Sequence[SearchHit]) -> Sequence[SearchHit]:
        if not hits:
            return ()
        query_tokens = set(query.casefold().split())
        reranked: list[SearchHit] = []
        for hit in hits:
            overlap = sum(1 for token in hit.chunk.text.casefold().split() if token in query_tokens)
            score = float(overlap)
            reranked.append(
                SearchHit(
                    chunk=hit.chunk,
                    score=score,
                    dense_score=hit.dense_score,
                    lexical_score=hit.lexical_score,
                    rerank_score=score,
                )
            )
        return sort_by_score(reranked)
