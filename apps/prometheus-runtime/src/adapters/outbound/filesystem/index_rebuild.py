"""Side-by-side Vault index rebuild with atomic filesystem promotion."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from adapters.outbound.qdrant.adapter import QdrantLocalVectorIndex
from adapters.outbound.sqlite.database import MetadataDatabase
from application.dto.embedding import EmbeddingFingerprint
from application.dto.index_fingerprint import IndexFingerprint
from application.ports.chunker import Chunker
from application.ports.document_repository import DocumentRepository
from application.ports.embedder import Embedder
from application.ports.index_metadata_store import IndexMetadataStore
from application.ports.markdown_parser import MarkdownParser
from application.ports.unit_of_work import UnitOfWork
from application.ports.vector_index import VectorIndex
from application.use_cases.index_document import IndexDocument
from application.use_cases.rename_document import RenameDocument
from domain.value_objects.vault_id import VaultId

REBUILD_DIRNAME = "rebuild"
_PREVIOUS_DIRNAME = ".previous"
_ACTIVE_NAMES = ("metadata.sqlite", "qdrant", "qdrant_metadata.json")


@dataclass(slots=True)
class FilesystemIndexRebuildSession:
    """Staging adapters rooted under ``vault_dir/rebuild``."""

    index_document: IndexDocument
    document_repository: DocumentRepository
    vector_index: VectorIndex
    index_metadata_store: IndexMetadataStore
    unit_of_work: UnitOfWork
    _vault_dir: Path
    _staging_dir: Path
    _database: MetadataDatabase
    _release_active: Callable[[], None]
    _closed: bool = False

    def promote(self) -> None:
        """Replace the active index with staging, then delete leftovers."""

        self._close_resources()
        self._release_active()
        previous = self._vault_dir / _PREVIOUS_DIRNAME
        if previous.exists():
            shutil.rmtree(previous)
        previous.mkdir(mode=0o700, parents=True, exist_ok=True)
        for name in _ACTIVE_NAMES:
            source = self._vault_dir / name
            if source.exists():
                source.rename(previous / name)
        for name in _ACTIVE_NAMES:
            source = self._staging_dir / name
            if source.exists():
                source.rename(self._vault_dir / name)
        if self._staging_dir.exists():
            shutil.rmtree(self._staging_dir)
        if previous.exists():
            shutil.rmtree(previous)

    def discard(self) -> None:
        """Drop staging data and leave the active index untouched."""

        self._close_resources()
        if self._staging_dir.exists():
            shutil.rmtree(self._staging_dir)

    def _close_resources(self) -> None:
        if self._closed:
            return
        close = getattr(self.vector_index, "close", None)
        if callable(close):
            close()
        self._database.close()
        self._closed = True


class FilesystemIndexRebuildWorkspace:
    """Create a staging Vault directory beside the active index files."""

    def __init__(
        self,
        vault_dir: Path,
        *,
        embedding_fingerprint: EmbeddingFingerprint,
        build_index_document: Callable[
            [DocumentRepository, VectorIndex, IndexMetadataStore, UnitOfWork],
            IndexDocument,
        ],
        release_active_storage: Callable[[], None],
    ) -> None:
        self._vault_dir = vault_dir.expanduser().resolve()
        self._embedding = embedding_fingerprint
        self._build_index_document = build_index_document
        self._release_active = release_active_storage

    def begin(self) -> FilesystemIndexRebuildSession:
        staging_dir = self._vault_dir / REBUILD_DIRNAME
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        database = MetadataDatabase(staging_dir)
        vector_index = QdrantLocalVectorIndex(
            vault_dir=staging_dir,
            embedding_fingerprint=self._embedding,
        )
        unit_of_work = database.unit_of_work()
        index_document = self._build_index_document(
            database.documents,
            vector_index,
            database.index_metadata,
            unit_of_work,
        )
        return FilesystemIndexRebuildSession(
            index_document=index_document,
            document_repository=database.documents,
            vector_index=vector_index,
            index_metadata_store=database.index_metadata,
            unit_of_work=unit_of_work,
            _vault_dir=self._vault_dir,
            _staging_dir=staging_dir,
            _database=database,
            _release_active=self._release_active,
        )


def build_staging_index_document(
    *,
    vault_id: VaultId,
    parser: MarkdownParser,
    chunker: Chunker,
    embedder: Embedder,
    document_repository: DocumentRepository,
    vector_index: VectorIndex,
    index_metadata_store: IndexMetadataStore,
    unit_of_work: UnitOfWork,
    active_fingerprint: IndexFingerprint,
    max_document_chars: int,
    max_chunks_per_document: int,
) -> IndexDocument:
    """Assemble an IndexDocument bound to staging storage ports."""

    rename = RenameDocument(
        document_repository=document_repository,
        vector_index=vector_index,
        unit_of_work=unit_of_work,
    )
    return IndexDocument(
        vault_id=vault_id,
        parser=parser,
        chunker=chunker,
        embedder=embedder,
        vector_index=vector_index,
        document_repository=document_repository,
        unit_of_work=unit_of_work,
        index_metadata_store=index_metadata_store,
        active_fingerprint=active_fingerprint,
        rename_document=rename,
        max_document_chars=max_document_chars,
        max_chunks_per_document=max_chunks_per_document,
    )
