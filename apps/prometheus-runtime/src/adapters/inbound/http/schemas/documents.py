"""HTTP schemas for document indexing operations."""

from datetime import datetime

from pydantic import Field

from adapters.inbound.http.schemas.common import ApiSchema
from application.dto.indexing import IndexDocumentResult, RemoveDocumentResult
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId


class DocumentUpsertRequest(ApiSchema):
    path: str = Field(examples=["Notes/Architecture.md"])
    content: str
    revision: int = Field(ge=0)
    modified_at: datetime

    def to_domain(self, vault_id: VaultId, document_id: DocumentId) -> Document:
        return Document.create(
            id=document_id,
            vault_id=vault_id,
            relative_path=self.path,
            content=self.content,
            revision=self.revision,
            modified_at=self.modified_at,
        )


class IndexDocumentResponse(ApiSchema):
    document_id: str
    skipped: bool
    relocated: bool
    created_chunks: int
    deleted_chunks: int

    @classmethod
    def from_dto(cls, result: IndexDocumentResult) -> "IndexDocumentResponse":
        return cls(
            document_id=result.document_id.value,
            skipped=result.skipped,
            relocated=result.relocated,
            created_chunks=result.created_chunks,
            deleted_chunks=result.deleted_chunks,
        )


class RemoveDocumentResponse(ApiSchema):
    document_id: str
    removed: bool
    removed_chunks: int

    @classmethod
    def from_dto(cls, result: RemoveDocumentResult) -> "RemoveDocumentResponse":
        return cls(
            document_id=result.document_id.value,
            removed=result.removed,
            removed_chunks=result.removed_chunks,
        )
