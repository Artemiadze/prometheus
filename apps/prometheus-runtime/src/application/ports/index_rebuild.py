"""Application port for side-by-side Vault index rebuilds."""

from __future__ import annotations

from typing import Protocol

from application.ports.document_repository import DocumentRepository
from application.ports.index_metadata_store import IndexMetadataStore
from application.ports.unit_of_work import UnitOfWork
from application.ports.vector_index import VectorIndex
from application.use_cases.index_document import IndexDocument


class IndexRebuildSession(Protocol):
    """Writable staging index that can be promoted or discarded."""

    @property
    def index_document(self) -> IndexDocument: ...

    @property
    def document_repository(self) -> DocumentRepository: ...

    @property
    def vector_index(self) -> VectorIndex: ...

    @property
    def index_metadata_store(self) -> IndexMetadataStore: ...

    @property
    def unit_of_work(self) -> UnitOfWork: ...

    def promote(self) -> None:
        """Atomically replace the active index with this staging index."""

    def discard(self) -> None:
        """Drop staging data without touching the active index."""


class IndexRebuildWorkspace(Protocol):
    """Open an isolated staging area for a full Vault rebuild."""

    def begin(self) -> IndexRebuildSession: ...
