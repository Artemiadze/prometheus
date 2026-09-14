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
