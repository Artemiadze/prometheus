"""Tests for BR-4 grounded prompt construction and token budgeting (PRM-44)."""

from __future__ import annotations

from application.services.grounded_prompt import (
    _CHAT_ROLE_OVERHEAD,
    build_grounded_prompt,
)
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import compute_content_hash
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.source_reference import SourceReference
from fakes.fake_token_counter import FakeTokenCounter


def _chunk(document_id: DocumentId, index: int, text: str, heading: str) -> Chunk:
    return Chunk(
        id=ChunkId.from_parts(document_id, (heading,), 1, index),
        document_id=document_id,
        text=text,
        heading_path=(heading,),
        chunk_index=index,
        char_range=CharRange(index * 100, index * 100 + len(text)),
        token_count=len(text.split()),
        content_hash=compute_content_hash(text),
        heading_line=0,
        heading_occurrence=1,
    )


def test_prompt_splits_system_rules_and_numbered_user_context() -> None:
    document_id = DocumentId("document-01")
    chunk = _chunk(document_id, 0, "Use multi-stage Docker builds.", "Images")

    prompt = build_grounded_prompt(
        question="How can I reduce image size?",
        chunks=(chunk,),
        document_paths={document_id: RelativePath("Docker/Optimization.md")},
        token_counter=FakeTokenCounter(),
        context_size=256,
        response_token_reserve=32,
    )

    assert "Answer using only the context fragments provided in the user message." in prompt.system
    assert "Reply in English." in prompt.system
    assert "Use at most three sentences" in prompt.system
    assert "Context:" in prompt.user
    assert "[1] Source: Docker/Optimization.md#Images" in prompt.user
    assert chunk.text in prompt.user
    assert "Question:\nHow can I reduce image size?" in prompt.user
    assert prompt.included_chunks == (chunk,)
    assert prompt.sources == (
        SourceReference.create(
            "Docker/Optimization.md",
            "Images",
            heading_line=0,
            heading_occurrence=1,
        ),
    )


def test_chunks_that_do_not_fit_are_excluded_from_prompt_and_sources() -> None:
    first_id = DocumentId("document-01")
    second_id = DocumentId("document-02")
    first = _chunk(first_id, 0, "short relevant context", "First")
    second = _chunk(second_id, 0, "extra context that cannot fit", "Second")
    paths = {
        first_id: RelativePath("Notes/First.md"),
        second_id: RelativePath("Notes/Second.md"),
    }
    counter = FakeTokenCounter()
    first_only = build_grounded_prompt(
        question="Question?",
        chunks=(first,),
        document_paths=paths,
        token_counter=counter,
        context_size=256,
        response_token_reserve=32,
    )
    exact_context_size = first_only.token_count + 32

    prompt = build_grounded_prompt(
        question="Question?",
        chunks=(first, second),
        document_paths=paths,
        token_counter=counter,
        context_size=exact_context_size,
        response_token_reserve=32,
    )

    assert prompt.token_count <= exact_context_size - 32
    assert prompt.included_chunks == (first,)
    assert prompt.sources == (
        SourceReference.create(
            "Notes/First.md",
            "First",
            heading_line=0,
            heading_occurrence=1,
        ),
    )
    assert second.text not in prompt.user
    assert "Notes/Second.md" not in prompt.user


def test_smaller_later_chunk_can_use_budget_after_oversized_chunk_is_skipped() -> None:
    document_id = DocumentId("document-01")
    oversized = _chunk(document_id, 0, "word " * 100, "Large")
    small = _chunk(document_id, 1, "small context", "Small")

    prompt = build_grounded_prompt(
        question="Question?",
        chunks=(oversized, small),
        document_paths={document_id: RelativePath("Notes/One.md")},
        token_counter=FakeTokenCounter(),
        context_size=200,
        response_token_reserve=16,
    )

    assert prompt.included_chunks == (small,)
    assert "[1] Source: Notes/One.md#Small" in prompt.user


def test_empty_context_still_produces_a_grounded_insufficiency_prompt() -> None:
    counter = FakeTokenCounter()

    prompt = build_grounded_prompt(
        question="Unknown?",
        chunks=(),
        document_paths={},
        token_counter=counter,
        context_size=256,
        response_token_reserve=32,
    )

    assert prompt.included_chunks == ()
    assert prompt.sources == ()
    assert "No context fragments were included." in prompt.user
    expected = counter.count(prompt.system) + counter.count(prompt.user) + _CHAT_ROLE_OVERHEAD
    assert prompt.token_count == expected
