"""Tests for pure BR-4 grounding policy rules."""

import pytest

from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import compute_content_hash
from domain.entities.search_hit import SearchHit
from domain.errors import InvariantViolationError
from domain.services.grounding_policy import GroundingPolicy
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath

pytestmark = pytest.mark.domain


def _hit(index: int, score: float, document_id: DocumentId | None = None) -> SearchHit:
    owner = document_id or DocumentId("document-01")
    text = f"Relevant chunk {index}"
    chunk = Chunk(
        id=ChunkId.from_parts(owner, ("Topic",), 1, index),
        document_id=owner,
        text=text,
        heading_path=("Topic",),
        chunk_index=index,
        char_range=CharRange(index * 100, index * 100 + len(text)),
        token_count=3,
        content_hash=compute_content_hash(text),
        heading_line=0,
        heading_occurrence=1,
    )
    return SearchHit(chunk, score)


def test_empty_retrieval_is_insufficient() -> None:
    selection = GroundingPolicy().select_context(())

    assert selection.hits == ()
    assert selection.insufficient_context


def test_hits_below_threshold_are_excluded() -> None:
    selection = GroundingPolicy(min_score=0.5).select_context(
        (_hit(0, 0.49), _hit(1, 0.5))
    )

    assert tuple(hit.score for hit in selection.hits) == (0.5,)
    assert not selection.insufficient_context


def test_minimum_relevant_chunk_count_controls_sufficiency() -> None:
    selection = GroundingPolicy(min_relevant_chunks=2).select_context((_hit(0, 0.9),))

    assert selection.insufficient_context


def test_context_is_sorted_and_limited_deterministically() -> None:
    hits = (_hit(0, 0.6), _hit(1, 0.9), _hit(2, 0.7))

    selection = GroundingPolicy(max_context_chunks=2).select_context(hits)

    assert tuple(hit.chunk.chunk_index for hit in selection.hits) == (1, 2)


def test_sources_come_only_from_selected_chunks_and_are_deduplicated() -> None:
    document_id = DocumentId("document-01")
    policy = GroundingPolicy(min_score=0.5)

    sources = policy.build_sources(
        (_hit(0, 0.9, document_id), _hit(1, 0.8, document_id), _hit(2, 0.4)),
        {document_id: RelativePath("Notes/Topic.md")},
    )

    assert len(sources) == 1
    assert sources[0].relative_path == RelativePath("Notes/Topic.md")
    assert sources[0].heading == "Topic"


def test_missing_document_path_is_a_domain_error() -> None:
    with pytest.raises(InvariantViolationError):
        GroundingPolicy().build_sources((_hit(0, 0.9),), {})
