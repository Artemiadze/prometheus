"""Library-independent DTOs exchanged by Markdown processing ports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from domain.entities.chunk import CharRange
from domain.errors import InvariantViolationError
from domain.value_objects.document_id import DocumentId


class BlockKind(StrEnum):
    """Markdown block categories preserved by the parser."""

    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    CODE = "code"
    QUOTE = "quote"


@dataclass(frozen=True, slots=True)
class ParsedBlock:
    """One source-positioned Markdown block."""

    kind: BlockKind
    text: str
    char_range: CharRange

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise InvariantViolationError()


@dataclass(frozen=True, slots=True)
class ParsedSection:
    """Blocks grouped under one complete heading path."""

    heading_path: tuple[str, ...]
    level: int
    blocks: tuple[ParsedBlock, ...]

    def __post_init__(self) -> None:
        headings = tuple(self.heading_path)
        blocks = tuple(self.blocks)
        object.__setattr__(self, "heading_path", headings)
        object.__setattr__(self, "blocks", blocks)
        if not 0 <= self.level <= 6 or any(not heading.strip() for heading in headings):
            raise InvariantViolationError()
        if self.level == 0 and headings:
            raise InvariantViolationError()
        if self.level > 0 and not headings:
            raise InvariantViolationError()


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Structured Markdown ready for heading-aware chunking."""

    document_id: DocumentId
    sections: tuple[ParsedSection, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sections", tuple(self.sections))
