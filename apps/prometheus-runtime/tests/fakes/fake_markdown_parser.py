"""Minimal MarkdownParser fake."""

from application.dto.parsed_document import (
    BlockKind,
    ParsedBlock,
    ParsedDocument,
    ParsedSection,
)
from domain.entities.chunk import CharRange
from domain.entities.document import Document


class FakeMarkdownParser:
    """Represent a non-empty document as one paragraph in a preamble section."""

    def parse(self, document: Document) -> ParsedDocument:
        if not document.content.strip():
            return ParsedDocument(document.id, ())
        block = ParsedBlock(
            kind=BlockKind.PARAGRAPH,
            text=document.content,
            char_range=CharRange(0, len(document.content)),
        )
        return ParsedDocument(
            document_id=document.id,
            sections=(ParsedSection(heading_path=(), level=0, blocks=(block,)),),
        )
