"""Chunk entity preserving Markdown structure and source position."""

from __future__ import annotations

from dataclasses import dataclass

from domain.entities.document import compute_content_hash
from domain.errors import InvariantViolationError
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId


@dataclass(frozen=True, slots=True)
class CharRange:
    """Half-open character range in the normalized source document."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise InvariantViolationError()


@dataclass(frozen=True, slots=True)
class Chunk:
    """A non-empty retrieval unit produced from one Document."""

    id: ChunkId
    document_id: DocumentId
    text: str
    heading_path: tuple[str, ...]
    chunk_index: int
    char_range: CharRange
    token_count: int
    content_hash: str
    heading_line: int | None = None
    heading_occurrence: int | None = None

    def __post_init__(self) -> None:
        headings = tuple(self.heading_path)
        object.__setattr__(self, "heading_path", headings)
        if (
            not self.text.strip()
            or self.chunk_index < 0
            or self.token_count <= 0
            or any(not heading.strip() for heading in headings)
            or self.content_hash != compute_content_hash(self.text)
        ):
            raise InvariantViolationError()
        if headings:
            if self.heading_line is None or self.heading_occurrence is None:
                raise InvariantViolationError()
            if self.heading_line < 0 or self.heading_occurrence < 1:
                raise InvariantViolationError()
        elif self.heading_line is not None or self.heading_occurrence is not None:
            raise InvariantViolationError()

    @property
    def heading(self) -> str | None:
        """Return the nearest heading when the chunk belongs to a section."""

        return self.heading_path[-1] if self.heading_path else None
