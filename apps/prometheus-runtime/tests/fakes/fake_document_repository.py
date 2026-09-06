"""In-memory DocumentRepository for unit tests."""

from collections.abc import Iterable, Sequence

from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath


class FakeDocumentRepository:
    """Store documents in a dictionary scoped to one test Vault."""

    def __init__(self, documents: Iterable[Document] = ()) -> None:
        self.documents = {document.id: document for document in documents}

    def get(self, document_id: DocumentId) -> Document | None:
        return self.documents.get(document_id)

    def list_relative_paths(self) -> Sequence[RelativePath]:
        return tuple(
            sorted(
                (document.relative_path for document in self.documents.values()),
                key=lambda path: path.value,
            )
        )

    def save(self, document: Document) -> None:
        """Seed or update state in a test setup."""

        self.documents[document.id] = document

    def delete(self, document_id: DocumentId) -> None:
        """Remove state in a test setup."""

        self.documents.pop(document_id, None)
