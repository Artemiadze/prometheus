"""Tests for scored retrieval results."""

from typing import cast

import pytest

from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import compute_content_hash
from domain.entities.search_hit import SearchHit, sort_by_score
from domain.errors import InvariantViolationError
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId

pytestmark = pytest.mark.domain


def _chunk(index: int) -> Chunk:
    document_id = DocumentId("document-01")
    text = f"Chunk {index}"
    return Chunk(
        id=ChunkId.from_parts(document_id, ("Heading",), index),
        document_id=document_id,
        text=text,
        heading_path=("Heading",),
        chunk_index=index,
        char_range=CharRange(index * 10, index * 10 + len(text)),
        token_count=2,
        content_hash=compute_content_hash(text),
    )


def test_partial_scores_are_optional() -> None:
    hit = SearchHit(_chunk(0), score=0.8)

    assert hit.score == 0.8
    assert hit.dense_score is None
    assert hit.lexical_score is None
    assert hit.rerank_score is None


def test_final_score_is_required_and_finite() -> None:
    with pytest.raises(InvariantViolationError):
        SearchHit(_chunk(0), score=cast(float, None))
    with pytest.raises(InvariantViolationError):
        SearchHit(_chunk(0), score=float("nan"))


def test_hits_sort_descending_and_stably() -> None:
    first_tied = SearchHit(_chunk(0), score=0.8)
    lower = SearchHit(_chunk(1), score=0.3)
    highest = SearchHit(_chunk(2), score=0.9)
    second_tied = SearchHit(_chunk(3), score=0.8)

    ordered = sort_by_score((first_tied, lower, highest, second_tied))

    assert ordered == (highest, first_tied, second_tied, lower)
