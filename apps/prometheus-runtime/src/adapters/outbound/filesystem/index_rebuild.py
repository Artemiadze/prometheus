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
from application.ports.lexical_index import LexicalIndex
from application.ports.markdown_parser import MarkdownParser
from application.ports.unit_of_work import UnitOfWork
from application.ports.vector_index import VectorIndex
from application.use_cases.index_document import IndexDocument
from application.use_cases.rename_document import RenameDocument
from domain.value_objects.vault_id import VaultId

REBUILD_DIRNAME = "rebuild"
PREVIOUS_DIRNAME = ".previous"
PROMOTE_MARKER = ".promote.lock"
_ACTIVE_NAMES = ("metadata.sqlite", "qdrant", "qdrant_metadata.json")

_PHASE_PREVIOUS = "previous"
_PHASE_ACTIVE = "active"
_PHASE_CLEANUP = "cleanup"


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _active_has_metadata(vault_dir: Path) -> bool:
    return (vault_dir / "metadata.sqlite").exists()


def recover_interrupted_promotion(vault_dir: Path) -> str | None:
    """Restore a consistent active index after a crash mid-promotion.

    Returns the recovery action taken, or ``None`` when nothing was needed.
    """

    root = vault_dir.expanduser().resolve()
    marker = root / PROMOTE_MARKER
    previous = root / PREVIOUS_DIRNAME
    staging = root / REBUILD_DIRNAME
    if not marker.exists() and not previous.exists():
        return None

    phase = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
    if phase == _PHASE_PREVIOUS or (previous.exists() and not _active_has_metadata(root)):
        for name in _ACTIVE_NAMES:
            _remove_path(root / name)
        for name in _ACTIVE_NAMES:
            source = previous / name
            if source.exists():
                source.rename(root / name)
        _remove_path(previous)
        _remove_path(marker)
        # Staging may still hold a partial rebuild; leave it for an explicit discard.
        return "restored-previous"

    if phase in {_PHASE_ACTIVE, _PHASE_CLEANUP} or (
        previous.exists() and _active_has_metadata(root)
    ):
        _remove_path(staging)
        _remove_path(previous)
        _remove_path(marker)
        return "finalized-active"

    _remove_path(marker)
    return None


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
        recover_interrupted_promotion(self._vault_dir)

        previous = self._vault_dir / PREVIOUS_DIRNAME
        marker = self._vault_dir / PROMOTE_MARKER
        _remove_path(previous)
        previous.mkdir(mode=0o700, parents=True, exist_ok=True)

        marker.write_text(_PHASE_PREVIOUS, encoding="utf-8")
        for name in _ACTIVE_NAMES:
            source = self._vault_dir / name
            if source.exists():
                source.rename(previous / name)

        marker.write_text(_PHASE_ACTIVE, encoding="utf-8")
        for name in _ACTIVE_NAMES:
            source = self._staging_dir / name
            if source.exists():
                source.rename(self._vault_dir / name)

        marker.write_text(_PHASE_CLEANUP, encoding="utf-8")
        _remove_path(self._staging_dir)
        _remove_path(previous)
        _remove_path(marker)

    def discard(self) -> None:
        """Drop staging data and leave the active index untouched."""

        self._close_resources()
        _remove_path(self._staging_dir)

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
        vault_id: VaultId,
        embedding_fingerprint: EmbeddingFingerprint,
        build_index_document: Callable[
            [DocumentRepository, VectorIndex, IndexMetadataStore, UnitOfWork, LexicalIndex],
            IndexDocument,
        ],
        release_active_storage: Callable[[], None],
    ) -> None:
        self._vault_dir = vault_dir.expanduser().resolve()
        self._vault_id = vault_id
        self._embedding = embedding_fingerprint
        self._build_index_document = build_index_document
        self._release_active = release_active_storage

    def begin(self) -> FilesystemIndexRebuildSession:
        recover_interrupted_promotion(self._vault_dir)
        staging_dir = self._vault_dir / REBUILD_DIRNAME
        _remove_path(staging_dir)
        staging_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        database = MetadataDatabase(staging_dir)
        vector_index = QdrantLocalVectorIndex(
            vault_dir=staging_dir,
            vault_id=self._vault_id,
            embedding_fingerprint=self._embedding,
        )
        unit_of_work = database.unit_of_work()
        index_document = self._build_index_document(
            database.documents,
            vector_index,
            database.index_metadata,
            unit_of_work,
            database.lexical,
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
    lexical_index: LexicalIndex,
    active_fingerprint: IndexFingerprint,
    max_document_chars: int,
    max_chunks_per_document: int,
) -> IndexDocument:
    """Assemble an IndexDocument bound to staging storage ports."""

    rename = RenameDocument(
        document_repository=document_repository,
        vector_index=vector_index,
        lexical_index=lexical_index,
        unit_of_work=unit_of_work,
    )
    return IndexDocument(
        vault_id=vault_id,
        parser=parser,
        chunker=chunker,
        embedder=embedder,
        vector_index=vector_index,
        lexical_index=lexical_index,
        document_repository=document_repository,
        unit_of_work=unit_of_work,
        index_metadata_store=index_metadata_store,
        active_fingerprint=active_fingerprint,
        rename_document=rename,
        max_document_chars=max_document_chars,
        max_chunks_per_document=max_chunks_per_document,
    )
