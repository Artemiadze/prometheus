"""HTTP schemas for full reindex requests."""

from datetime import datetime

from adapters.inbound.http.schemas.common import ApiSchema
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId


class ReindexDocumentRequest(ApiSchema):
    document_id: str
    path: str
    content: str
    revision: int
    modified_at: datetime

    def to_domain(self, vault_id: VaultId) -> Document:
        return Document.create(
            id=DocumentId(self.document_id),
            vault_id=vault_id,
            relative_path=self.path,
            content=self.content,
            revision=self.revision,
            modified_at=self.modified_at,
        )


class ReindexRequest(ApiSchema):
    documents: tuple[ReindexDocumentRequest, ...]

    def to_domain(self, vault_id: VaultId) -> tuple[Document, ...]:
        return tuple(document.to_domain(vault_id) for document in self.documents)
