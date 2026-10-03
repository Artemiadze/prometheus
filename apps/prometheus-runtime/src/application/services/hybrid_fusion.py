"""Weighted reciprocal rank fusion for dense and lexical retrieval lists."""

from __future__ import annotations

from collections.abc import Sequence

from domain.entities.search_hit import SearchHit
from domain.value_objects.chunk_id import ChunkId


def fuse_weighted_rrf(
    dense_hits: Sequence[SearchHit],
    lexical_hits: Sequence[SearchHit],
    *,
    k: int,
    dense_weight: float,
    lexical_weight: float,
) -> tuple[SearchHit, ...]:
    """Merge ranked lists by chunk id using weighted RRF scores."""

    dense_rank: dict[ChunkId, int] = {
        hit.chunk.id: rank for rank, hit in enumerate(dense_hits, start=1)
    }
    lexical_rank: dict[ChunkId, int] = {
        hit.chunk.id: rank for rank, hit in enumerate(lexical_hits, start=1)
    }
    dense_by_id: dict[ChunkId, SearchHit] = {hit.chunk.id: hit for hit in dense_hits}
    lexical_by_id: dict[ChunkId, SearchHit] = {hit.chunk.id: hit for hit in lexical_hits}

    all_ids = set(dense_rank) | set(lexical_rank)
    fused: list[SearchHit] = []
    for chunk_id in all_ids:
        score = 0.0
        if chunk_id in dense_rank:
            score += dense_weight / (k + dense_rank[chunk_id])
        if chunk_id in lexical_rank:
            score += lexical_weight / (k + lexical_rank[chunk_id])

        dense_hit = dense_by_id.get(chunk_id)
        lexical_hit = lexical_by_id.get(chunk_id)
        if dense_hit is not None:
            chunk = dense_hit.chunk
        elif lexical_hit is not None:
            chunk = lexical_hit.chunk
        else:
            continue
        fused.append(
            SearchHit(
                chunk=chunk,
                score=score,
                dense_score=dense_hit.dense_score if dense_hit is not None else None,
                lexical_score=lexical_hit.lexical_score if lexical_hit is not None else None,
                rerank_score=None,
            )
        )

    fused.sort(key=lambda hit: (-hit.score, hit.chunk.id.value))
    return tuple(fused)
