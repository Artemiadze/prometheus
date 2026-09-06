"""Tests for Chunk and its source character range."""

import pytest

from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import compute_content_hash
from domain.errors import InvariantViolationError
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId


def _chunk(text: str = "Index details") -> Chunk:
    document_id = DocumentId("document-01")
    return Chunk(
        id=ChunkId.from_parts(document_id, ("PostgreSQL", "Indexes"), 0),
        document_id=document_id,
        text=text,
        heading_path=("PostgreSQL", "Indexes"),
        chunk_index=0,
        char_range=CharRange(13, 13 + len(text)),
        token_count=2,
        content_hash=compute_content_hash(text),
    )


def test_heading_path_preserves_full_hierarchy() -> None:
    chunk = _chunk()

    assert chunk.heading_path == ("PostgreSQL", "Indexes")
    assert chunk.heading == "Indexes"


def test_whitespace_text_is_rejected() -> None:
    with pytest.raises(InvariantViolationError):
        _chunk("   \n")


def test_invalid_character_ranges_raise_domain_error() -> None:
    with pytest.raises(InvariantViolationError):
        CharRange(-1, 2)
    with pytest.raises(InvariantViolationError):
        CharRange(3, 3)


def test_character_range_recovers_source_position() -> None:
    source = "# PostgreSQL\nIndex details\n"
    chunk = _chunk()

    assert source[chunk.char_range.start : chunk.char_range.end] == chunk.text


def test_invalid_token_count_is_rejected() -> None:
    base = _chunk()

    with pytest.raises(InvariantViolationError):
        Chunk(
            id=base.id,
            document_id=base.document_id,
            text=base.text,
            heading_path=base.heading_path,
            chunk_index=base.chunk_index,
            char_range=base.char_range,
            token_count=0,
            content_hash=base.content_hash,
        )
