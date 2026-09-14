"""Aggregate counters for one Vault's index (Project_analytics.md, section 46)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.errors import InvariantViolationError


@dataclass(frozen=True, slots=True)
class IndexStatistics:
    """Document/chunk counts, recency, and on-disk size of one Vault's index."""

    document_count: int
    chunk_count: int
    last_indexed_at: datetime | None
    index_size_bytes: int

    def __post_init__(self) -> None:
        if self.document_count < 0 or self.chunk_count < 0 or self.index_size_bytes < 0:
            raise InvariantViolationError()
