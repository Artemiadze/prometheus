"""Vault snapshot and synchronization result DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.errors import InvariantViolationError
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath


@dataclass(frozen=True, slots=True)
class VaultSnapshotEntry:
    document_id: DocumentId
    relative_path: RelativePath
    content_hash: str
    revision: int
    modified_at: datetime

    def __post_init__(self) -> None:
        if self.revision < 0 or len(self.content_hash) != 64:
            raise InvariantViolationError()


@dataclass(frozen=True, slots=True)
class VaultSnapshot:
    entries: tuple[VaultSnapshotEntry, ...]

    def __post_init__(self) -> None:
        ids = [entry.document_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise InvariantViolationError()


@dataclass(frozen=True, slots=True)
class VaultSyncSummary:
    added: tuple[VaultSnapshotEntry, ...]
    changed: tuple[VaultSnapshotEntry, ...]
    renamed: tuple[VaultSnapshotEntry, ...]
    unchanged: tuple[VaultSnapshotEntry, ...]
    deleted: tuple[DocumentId, ...]
