"""Tests for grounded answers and source references."""

import pytest

from domain.entities.grounded_answer import GroundedAnswer
from domain.errors import InvariantViolationError
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.source_reference import SourceReference

pytestmark = pytest.mark.domain


def test_sufficient_answer_requires_a_source() -> None:
    with pytest.raises(InvariantViolationError):
        GroundedAnswer.create(text="Answer", insufficient_context=False)


def test_insufficient_answer_may_have_no_sources() -> None:
    answer = GroundedAnswer.create(
        text="There is not enough information in the notes.",
        insufficient_context=True,
    )

    assert answer.sources == ()


def test_answer_text_is_always_required() -> None:
    with pytest.raises(InvariantViolationError):
        GroundedAnswer.create(text="  ", insufficient_context=True)


def test_sources_are_deduplicated_by_path_and_heading_in_order() -> None:
    first = SourceReference.create("Docker/Optimization.md", "Multi-stage builds")
    duplicate = SourceReference.create("Docker/Optimization.md", "Multi-stage builds")
    second = SourceReference.create("Backend/Containers.md", "Images")

    answer = GroundedAnswer.create(
        text="Use a multi-stage build.",
        sources=(first, duplicate, second, first),
        used_chunk_ids=(ChunkId("chunk-01"),),
        insufficient_context=False,
    )

    assert answer.sources == (first, second)


def test_blank_heading_is_normalized_to_none() -> None:
    source = SourceReference.create("Note.md", "   ")

    assert source.heading is None
