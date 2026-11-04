"""In-memory IndexRebuildWorkspace for unit tests."""

from __future__ import annotations

from dataclasses import dataclass

from application.dto.index_fingerprint import IndexFingerprint
from application.ports.document_repository import DocumentRepository
from application.ports.index_metadata_store import IndexMetadataStore
from application.ports.unit_of_work import UnitOfWork
from application.ports.vector_index import VectorIndex
from application.use_cases.index_document import IndexDocument
from application.use_cases.rename_document import RenameDocument
from domain.value_objects.vault_id import VaultId
from fakes.fake_chunker import FakeChunker
from fakes.fake_document_repository import FakeDocumentRepository
from fakes.fake_embedder import FakeEmbedder
from fakes.fake_index_metadata_store import FakeIndexMetadataStore
from fakes.fake_markdown_parser import FakeMarkdownParser
from fakes.fake_unit_of_work import FakeUnitOfWork
from fakes.fake_vector_index import FakeVectorIndex


@dataclass(slots=True)
class FakeIndexRebuildSession:
    index_document: IndexDocument
    document_repository: DocumentRepository
    vector_index: VectorIndex
    index_metadata_store: IndexMetadataStore
    unit_of_work: UnitOfWork
    _active_documents: FakeDocumentRepository
    _active_vectors: FakeVectorIndex
    _active_metadata: FakeIndexMetadataStore
    _promoted: bool = False
    _discarded: bool = False

    def promote(self) -> None:
        self._active_documents._states.clear()
        self._active_documents._states.update(self.document_repository._states)  # type: ignore[attr-defined]
        self._active_documents._fingerprints.clear()
        self._active_documents._fingerprints.update(
            self.document_repository._fingerprints  # type: ignore[attr-defined]
        )
        self._active_vectors._documents.clear()
        self._active_vectors._documents.update(self.vector_index._documents)  # type: ignore[attr-defined]
        self._active_vectors._document_paths.clear()
        self._active_vectors._document_paths.update(
            self.vector_index._document_paths  # type: ignore[attr-defined]
        )
        self._active_metadata._fingerprint = self.index_metadata_store.load()
        self._promoted = True

    def discard(self) -> None:
        self._discarded = True


class FakeIndexRebuildWorkspace:
    def __init__(
        self,
        *,
        vault_id: VaultId,
        active_documents: FakeDocumentRepository,
        active_vectors: FakeVectorIndex,
        active_metadata: FakeIndexMetadataStore,
        embedder: FakeEmbedder,
        parser: FakeMarkdownParser,
        chunker: FakeChunker,
        fingerprint: IndexFingerprint,
        max_document_chars: int = 2_000_000,
        max_chunks_per_document: int = 10_000,
        reuse_active_embeddings: bool = True,
    ) -> None:
        self._vault_id = vault_id
        self._active_documents = active_documents
        self._active_vectors = active_vectors
        self._active_metadata = active_metadata
        self._embedder = embedder
        self._parser = parser
        self._chunker = chunker
        self._fingerprint = fingerprint
        self._max_document_chars = max_document_chars
        self._max_chunks_per_document = max_chunks_per_document
        self._reuse_active_embeddings = reuse_active_embeddings
        self.last_session: FakeIndexRebuildSession | None = None

    def begin(self) -> FakeIndexRebuildSession:
        documents = FakeDocumentRepository()
        vectors = FakeVectorIndex()
        metadata = FakeIndexMetadataStore()
        unit_of_work = FakeUnitOfWork()
        rename = RenameDocument(
            document_repository=documents,
            vector_index=vectors,
            lexical_index=None,
            unit_of_work=unit_of_work,
        )
        reuse_documents = None
        reuse_vectors = None
        stored = self._active_metadata.load()
        if (
            self._reuse_active_embeddings
            and stored is not None
            and stored.embedding == self._fingerprint.embedding
        ):
            reuse_documents = self._active_documents
            reuse_vectors = self._active_vectors
        index_document = IndexDocument(
            vault_id=self._vault_id,
            parser=self._parser,
            chunker=self._chunker,
            embedder=self._embedder,
            vector_index=vectors,
            lexical_index=None,
            document_repository=documents,
            unit_of_work=unit_of_work,
            index_metadata_store=metadata,
            active_fingerprint=self._fingerprint,
            rename_document=rename,
            max_document_chars=self._max_document_chars,
            max_chunks_per_document=self._max_chunks_per_document,
            reuse_document_repository=reuse_documents,
            reuse_vector_index=reuse_vectors,
        )
        session = FakeIndexRebuildSession(
            index_document=index_document,
            document_repository=documents,
            vector_index=vectors,
            index_metadata_store=metadata,
            unit_of_work=unit_of_work,
            _active_documents=self._active_documents,
            _active_vectors=self._active_vectors,
            _active_metadata=self._active_metadata,
        )
        self.last_session = session
        return session
