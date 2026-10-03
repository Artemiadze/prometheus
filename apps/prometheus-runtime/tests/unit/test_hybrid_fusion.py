"""Tests for weighted RRF fusion."""

from __future__ import annotations

import pytest

from application.services.hybrid_fusion import fuse_weighted_rrf
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import compute_content_hash
from domain.entities.search_hit import SearchHit
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId


def _chunk(index: int) -> Chunk:
    document_id = DocumentId("document-01")
    text = f"Chunk {index}"
    return Chunk(
        id=ChunkId.from_parts(document_id, ("Heading",), 1, index),
        document_id=document_id,
        text=text,
        heading_path=("Heading",),
        chunk_index=index,
        char_range=CharRange(index * 10, index * 10 + len(text)),
        token_count=2,
        content_hash=compute_content_hash(text),
        heading_line=0,
        heading_occurrence=1,
    )


def _hit(
    chunk_index: int, *, dense: float | None = None, lexical: float | None = None
) -> SearchHit:
    chunk = _chunk(chunk_index)
    score = dense if dense is not None else lexical if lexical is not None else 0.5
    return SearchHit(
        chunk=chunk,
        score=score,
        dense_score=dense,
        lexical_score=lexical,
    )


def test_fusion_computes_weighted_rrf_for_overlap() -> None:
    k = 60
    w_d = 1.0
    w_l = 1.0
    dense = (_hit(0, dense=0.9), _hit(1, dense=0.5))
    lexical = (_hit(1, lexical=2.0), _hit(0, lexical=1.0))

    fused = fuse_weighted_rrf(dense, lexical, k=k, dense_weight=w_d, lexical_weight=w_l)

    expected_0 = w_d / (k + 1) + w_l / (k + 2)
    expected_1 = w_d / (k + 2) + w_l / (k + 1)
    by_index = {hit.chunk.chunk_index: hit for hit in fused}
    assert by_index[0].score == pytest.approx(expected_0)
    assert by_index[0].dense_score == pytest.approx(0.9)
    assert by_index[0].lexical_score == pytest.approx(1.0)
    assert by_index[1].score == pytest.approx(expected_1)
    assert fused[0].score >= fused[1].score


def test_fusion_includes_single_channel_hits() -> None:
    k = 60
    dense = (_hit(0, dense=0.9),)
    lexical = (_hit(1, lexical=1.5),)

    fused = fuse_weighted_rrf(dense, lexical, k=k, dense_weight=1.0, lexical_weight=1.0)

    assert len(fused) == 2
    scores = {hit.chunk.chunk_index: hit.score for hit in fused}
    assert scores[0] == pytest.approx(1.0 / (k + 1))
    assert scores[1] == pytest.approx(1.0 / (k + 1))
    by_index = {hit.chunk.chunk_index: hit for hit in fused}
    assert by_index[0].dense_score is not None
    assert by_index[0].lexical_score is None
    assert by_index[1].lexical_score is not None
    assert by_index[1].dense_score is None


def test_fusion_tie_breaks_by_chunk_id_value() -> None:
    k = 60
    dense = (_hit(0, dense=0.9),)
    lexical = (_hit(1, lexical=1.5),)
    fused = fuse_weighted_rrf(dense, lexical, k=k, dense_weight=1.0, lexical_weight=1.0)
    assert fused[0].score == pytest.approx(fused[1].score)
    assert fused[0].chunk.id.value <= fused[1].chunk.id.value
