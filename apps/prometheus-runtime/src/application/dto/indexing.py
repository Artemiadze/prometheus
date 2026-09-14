"""Results and progress values for indexing use cases."""

from __future__ import annotations

from dataclasses import dataclass

from application.dto.job import Job
from domain.errors import InvariantViolationError
from domain.value_objects.document_id import DocumentId


@dataclass(frozen=True, slots=True)
class IndexDocumentResult:
    document_id: DocumentId
    created_chunks: int
    deleted_chunks: int
    skipped: bool = False
    relocated: bool = False

    def __post_init__(self) -> None:
        if self.created_chunks < 0 or self.deleted_chunks < 0:
            raise InvariantViolationError()


@dataclass(frozen=True, slots=True)
class RemoveDocumentResult:
    document_id: DocumentId
    removed: bool
    removed_chunks: int

    def __post_init__(self) -> None:
        if self.removed_chunks < 0:
            raise InvariantViolationError()


@dataclass(frozen=True, slots=True)
class IndexingProgress:
    processed_documents: int
    total_documents: int
    processed_chunks: int

    def __post_init__(self) -> None:
        if (
            self.processed_documents < 0
            or self.total_documents < 0
            or self.processed_documents > self.total_documents
            or self.processed_chunks < 0
        ):
            raise InvariantViolationError()

    @property
    def ratio(self) -> float:
        return 1.0 if self.total_documents == 0 else self.processed_documents / self.total_documents


@dataclass(frozen=True, slots=True)
class ReindexResult:
    job: Job
    processed_documents: int
    processed_chunks: int
    cancelled: bool
