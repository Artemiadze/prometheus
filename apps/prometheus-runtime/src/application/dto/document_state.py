"""Manifest snapshot for one indexed Document, without its note text."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.errors import InvariantViolationError
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath


@dataclass(frozen=True, slots=True)
class DocumentState:
    """Manifest row: identity, hash, and indexing bookkeeping for one Document."""

    document_id: DocumentId
    relative_path: RelativePath
    revision: int
    content_hash: str
    modified_at: datetime
    indexed_at: datetime
    chunk_count: int

    def __post_init__(self) -> None:
        if self.revision < 0 or self.chunk_count < 0 or not self.content_hash.strip():
            raise InvariantViolationError()
