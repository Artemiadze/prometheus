"""Temporary paragraph parser until the heading-aware PRM-E4 parser exists."""

from __future__ import annotations

import re

from application.dto.parsed_document import BlockKind, ParsedBlock, ParsedDocument, ParsedSection
from domain.entities.chunk import CharRange
from domain.entities.document import Document

_PARAGRAPH = re.compile(r"\S(?:.*?\S)?(?=\s*\n\s*\n|\s*\Z)", re.DOTALL)


class ParagraphMarkdownParser:
    """Parse non-empty paragraphs into one unheaded section."""

    def parse(self, document: Document) -> ParsedDocument:
        blocks = [
            ParsedBlock(
                BlockKind.PARAGRAPH,
                match.group(),
                CharRange(match.start(), match.end()),
            )
            for match in _PARAGRAPH.finditer(document.content)
        ]
        sections = () if not blocks else (ParsedSection((), 0, tuple(blocks)),)
        return ParsedDocument(document.id, sections)
