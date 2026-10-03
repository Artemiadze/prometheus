"""Presentation-neutral semantic search result."""

from dataclasses import dataclass

from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath


@dataclass(frozen=True, slots=True)
class SearchResult:
    document_id: DocumentId
    chunk_id: ChunkId
    relative_path: RelativePath
    heading: str | None
    text: str
    score: float
    heading_line: int | None = None
    heading_occurrence: int | None = None

    @property
    def link(self) -> str:
        base = self.relative_path.value
        if self.heading is None:
            return base
        return f"{base}#{self.heading}"
