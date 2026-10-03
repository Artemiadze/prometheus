"""Lexical chunk search application port."""

from collections.abc import Sequence
from typing import Protocol

from domain.entities.chunk import Chunk
from domain.entities.document import Document
from domain.entities.search_hit import SearchHit
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import SearchScope


class LexicalIndex(Protocol):
    """BM25-style lexical retrieval over indexed chunk text."""

    def replace_document(self, document: Document, chunks: Sequence[Chunk]) -> None: ...

    def delete_by_document(self, document_id: DocumentId) -> None: ...

    def update_document_path(
        self,
        document_id: DocumentId,
        relative_path: RelativePath,
    ) -> None: ...

    def search(
        self,
        query: str,
        limit: int,
        scope: SearchScope | None = None,
    ) -> Sequence[SearchHit]: ...
