"""Document persistence application port."""

from collections.abc import Sequence
from typing import Protocol

from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath


class DocumentRepository(Protocol):
    """Read document state within one already-scoped Vault."""

    def get(self, document_id: DocumentId) -> Document | None: ...

    def list_relative_paths(self) -> Sequence[RelativePath]: ...
