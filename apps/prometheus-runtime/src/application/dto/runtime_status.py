"""Aggregate runtime status DTO."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class IndexState(StrEnum):
    NOT_INDEXED = "not_indexed"
    READY = "ready"
    REBUILD_REQUIRED = "rebuild_required"
    CORRUPTED = "index_corrupted"


@dataclass(frozen=True, slots=True)
class RuntimeStatus:
    runtime_version: str
    index_state: IndexState
    llm_available: bool
    llm_model: str
    document_count: int
    chunk_count: int
    last_indexed_at: datetime | None
    index_size_bytes: int
