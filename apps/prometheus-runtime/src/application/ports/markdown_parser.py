"""Markdown parsing application port."""

from typing import Protocol

from application.dto.parsed_document import ParsedDocument
from domain.entities.document import Document


class MarkdownParser(Protocol):
    """Convert a Document into library-independent structured Markdown."""

    def parse(self, document: Document) -> ParsedDocument: ...
