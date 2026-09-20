"""HTTP schemas for complete Vault snapshots."""

from datetime import datetime

from adapters.inbound.http.schemas.common import ApiSchema
from application.dto.vault_sync import VaultSnapshot, VaultSnapshotEntry
from domain.value_objects.document_id import DocumentId


class VaultSnapshotEntryRequest(ApiSchema):
    document_id: str
    path: str
    content_hash: str
    revision: int
    modified_at: datetime

    def to_dto(self) -> VaultSnapshotEntry:
        from domain.value_objects.relative_path import RelativePath

        return VaultSnapshotEntry(
            document_id=DocumentId(self.document_id),
            relative_path=RelativePath(self.path),
            content_hash=self.content_hash,
            revision=self.revision,
            modified_at=self.modified_at,
        )


class VaultSyncRequest(ApiSchema):
    entries: tuple[VaultSnapshotEntryRequest, ...]

    def to_dto(self) -> VaultSnapshot:
        return VaultSnapshot(tuple(entry.to_dto() for entry in self.entries))


class JobStartedResponse(ApiSchema):
    job_id: str
    status_url: str
