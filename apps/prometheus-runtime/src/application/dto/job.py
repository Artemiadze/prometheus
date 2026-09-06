"""DTOs for background application jobs."""

import re
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from domain.errors import InvalidIdentifierError, InvariantViolationError

_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{5,127}$")


class JobStatus(StrEnum):
    """Lifecycle states exposed by the jobs API."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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
    status: JobStatus
    progress: float
    error: str | None = None

    def __post_init__(self) -> None:
        if not isfinite(self.progress) or not 0.0 <= self.progress <= 1.0:
            raise InvariantViolationError()
        if self.status is JobStatus.FAILED and not self.error:
            raise InvariantViolationError()
        if self.status is not JobStatus.FAILED and self.error is not None:
            raise InvariantViolationError()
