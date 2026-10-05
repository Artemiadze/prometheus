"""Tests for FastEmbed reranker adapter without loading an ONNX model."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from adapters.outbound.fastembed.errors import (
    RerankerBatchError,
    RerankerModelUnavailableError,
)
from adapters.outbound.fastembed.reranker import FastEmbedReranker
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import compute_content_hash
from domain.entities.search_hit import SearchHit
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId


class RecordingCrossEncoder:
    def __init__(self, scores: Sequence[float] | None = None, *, fail: bool = False) -> None:
        self.scores = scores
        self.fail = fail
        self.calls: list[tuple[str, tuple[str, ...], int]] = []

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        batch_size: int,
    ) -> Sequence[float]:
        self.calls.append((query, tuple(documents), batch_size))
        if self.fail:
            raise RuntimeError("backend failed")
        if self.scores is not None:
            return self.scores
        return tuple(float(len(document)) for document in documents)


class RecordingCrossEncoderFactory:
    def __init__(self, backend: RecordingCrossEncoder) -> None:
        self.backend = backend
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        *,
        model_name: str,
        cache_dir: str,
        threads: int | None,
    ) -> RecordingCrossEncoder:
        self.calls.append(
            {"model_name": model_name, "cache_dir": cache_dir, "threads": threads},
        )
        return self.backend


def _chunk(index: int, text: str) -> Chunk:
    document_id = DocumentId("document-01")
    return Chunk(
        id=ChunkId.from_parts(document_id, ("Heading",), 1, index),
        document_id=document_id,
        text=text,
        heading_path=("Heading",),
        chunk_index=index,
        char_range=CharRange(0, len(text)),
        token_count=3,
        content_hash=compute_content_hash(text),
        heading_line=0,
        heading_occurrence=1,
    )


def _hit(index: int, text: str, *, dense: float = 0.5) -> SearchHit:
    return SearchHit(chunk=_chunk(index, text), score=dense, dense_score=dense)


def test_rerank_orders_by_cross_encoder_scores(tmp_path: Path) -> None:
    backend = RecordingCrossEncoder(scores=(0.2, 0.9, 0.4))
    factory = RecordingCrossEncoderFactory(backend)
    reranker = FastEmbedReranker(
        model_id="Xenova/ms-marco-MiniLM-L-6-v2",
        cache_dir=tmp_path,
        backend_factory=factory,
        model_validator=lambda _model_id: None,
    )
    hits = (_hit(0, "alpha"), _hit(1, "beta"), _hit(2, "gamma"))

    ordered = reranker.rerank("query", hits)

    assert [hit.chunk.chunk_index for hit in ordered] == [1, 2, 0]
    assert ordered[0].rerank_score == pytest.approx(0.9)
    assert ordered[0].score == pytest.approx(0.9)
    assert ordered[0].dense_score == pytest.approx(0.5)
    assert backend.calls[0][2] == 32


def test_unsupported_model_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(RerankerModelUnavailableError):
        FastEmbedReranker(
            model_id="unknown/model",
            cache_dir=tmp_path,
            backend_factory=RecordingCrossEncoderFactory(RecordingCrossEncoder()),
            model_validator=lambda _model_id: (_ for _ in ()).throw(
                RerankerModelUnavailableError()
            ),
        )


def test_backend_failure_surfaces_safe_error(tmp_path: Path) -> None:
    reranker = FastEmbedReranker(
        model_id="Xenova/ms-marco-MiniLM-L-6-v2",
        cache_dir=tmp_path,
        backend_factory=RecordingCrossEncoderFactory(RecordingCrossEncoder(fail=True)),
        model_validator=lambda _model_id: None,
    )
    with pytest.raises(RerankerBatchError):
        reranker.rerank("query", (_hit(0, "alpha"),))
