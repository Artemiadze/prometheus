"""DTOs for background application jobs."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite

from domain.errors import InvalidIdentifierError, InvariantViolationError
from domain.value_objects.vault_id import VaultId

_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{5,127}$")


class JobStatus(StrEnum):
    """Lifecycle states exposed by the jobs API."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobKind(StrEnum):
    """Background operation category persisted with each job."""

    SYNC = "sync"
    REINDEX = "reindex"


@dataclass(frozen=True, slots=True)
class JobId:
    """Stable identifier for one background job."""

    value: str

    def __post_init__(self) -> None:
        if not _JOB_ID.fullmatch(self.value):
            raise InvalidIdentifierError()

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Job:
    """Serializable application state for a background operation."""

    id: JobId
    vault_id: VaultId
    kind: JobKind
    status: JobStatus
    progress: float
    processed_documents: int
    total_documents: int
    processed_chunks: int
    created_at: datetime
    updated_at: datetime
    error: str | None = None

    def __post_init__(self) -> None:
        if (
            not isfinite(self.progress)
            or not 0.0 <= self.progress <= 1.0
            or self.processed_documents < 0
            or self.total_documents < 0
            or self.processed_chunks < 0
            or self.processed_documents > self.total_documents
        ):
            raise InvariantViolationError()
        if self.status is JobStatus.FAILED and not self.error:
            raise InvariantViolationError()
        if self.status is not JobStatus.FAILED and self.error is not None:
            raise InvariantViolationError()

    def with_state(
        self,
        *,
        status: JobStatus,
        progress: float,
        error: str | None = None,
        processed_documents: int | None = None,
        total_documents: int | None = None,
        processed_chunks: int | None = None,
        updated_at: datetime,
    ) -> "Job":
        """Return a copy with updated lifecycle fields."""

        return Job(
            id=self.id,
            vault_id=self.vault_id,
            kind=self.kind,
            status=status,
            progress=progress,
            processed_documents=(
                self.processed_documents if processed_documents is None else processed_documents
            ),
            total_documents=self.total_documents if total_documents is None else total_documents,
            processed_chunks=(
                self.processed_chunks if processed_chunks is None else processed_chunks
            ),
            created_at=self.created_at,
            updated_at=updated_at,
            error=error,
        )
