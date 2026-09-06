"""Text chunking application port."""

from collections.abc import Sequence
from typing import Protocol

from application.dto.parsed_document import ParsedDocument
from domain.entities.chunk import Chunk


class Chunker(Protocol):
    """Produce domain Chunks from parsed Markdown structure."""

    def chunk(self, parsed_document: ParsedDocument) -> Sequence[Chunk]: ...
