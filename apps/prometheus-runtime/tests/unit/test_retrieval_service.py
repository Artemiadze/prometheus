"""Tests for dense and hybrid retrieval paths."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from application.dto.index_fingerprint import PAYLOAD_SCHEMA_VERSION, IndexFingerprint
from application.services.retrieval import RetrievalService
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document, compute_content_hash
from domain.entities.search_hit import SearchHit
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import SearchScope
from domain.value_objects.vault_id import VaultId
from fakes import (
    FakeDocumentRepository,
    FakeEmbedder,
    FakeIndexMetadataStore,
    FakeReranker,
    FakeVectorIndex,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 1, 1, tzinfo=UTC)
VAULT_ID = VaultId("vault-01")


class RecordingLexicalIndex:
    def __init__(self, hits: Sequence[SearchHit]) -> None:
        self._hits = tuple(hits)
        self.search_calls = 0

    def replace_document(self, document: Document, chunks: Sequence[Chunk]) -> None:
        raise NotImplementedError

    def delete_by_document(self, document_id: DocumentId) -> None:
        raise NotImplementedError

    def update_document_path(
        self, document_id: DocumentId, relative_path: RelativePath
    ) -> None:
        raise NotImplementedError

    def search(
        self,
        query: str,
        limit: int,
        scope: SearchScope | None = None,
    ) -> Sequence[SearchHit]:
        self.search_calls += 1
        return self._hits[:limit]


def _chunk(*, text: str, index: int = 0) -> Chunk:
    document_id = DocumentId("document-01")
    return Chunk(
        id=ChunkId.from_parts(document_id, ("Heading",), 1, index),
        document_id=document_id,
        text=text,
        heading_path=("Heading",),
        chunk_index=index,
        char_range=CharRange(0, len(text)),
        token_count=3,
        content_hash=compute_content_hash(text),
        heading_line=0,
        heading_occurrence=1,
    )


def _fingerprint(embedder: FakeEmbedder) -> IndexFingerprint:
    return IndexFingerprint(embedder.fingerprint, 1, 1, PAYLOAD_SCHEMA_VERSION, 700, 80)


def _indexed_metadata(metadata: FakeIndexMetadataStore, embedder: FakeEmbedder) -> None:
    metadata.save(_fingerprint(embedder))


def test_dense_mode_does_not_call_lexical_index() -> None:
    embedder = FakeEmbedder()
    documents = FakeDocumentRepository()
    vectors = FakeVectorIndex()
    metadata = FakeIndexMetadataStore()
    lexical = RecordingLexicalIndex(())
    document = Document.create(
        id=DocumentId("document-01"),
        vault_id=VAULT_ID,
        relative_path="Notes/One.md",
        content="semantic retrieval content",
        revision=1,
        modified_at=NOW,
    )
    _indexed_metadata(metadata, embedder)
    chunk = _chunk(text="semantic retrieval content")
    vectors.upsert(document, (chunk,), embedder.embed_documents((chunk,)))
    documents.save_indexed(document, (chunk,), NOW)

    retrieval = RetrievalService(
        embedder=embedder,
        vector_index=vectors,
        document_repository=documents,
        index_metadata_store=metadata,
        active_fingerprint=_fingerprint(embedder),
        lexical_index=lexical,
        retrieval_mode="dense",
    )
    results = asyncio.run(retrieval.retrieve("semantic", limit=5))

    assert results
    assert lexical.search_calls == 0


def test_hybrid_mode_surfaces_lexical_only_hit() -> None:
    embedder = FakeEmbedder()
    documents = FakeDocumentRepository()
    vectors = FakeVectorIndex()
    metadata = FakeIndexMetadataStore()
    document = Document.create(
        id=DocumentId("document-01"),
        vault_id=VAULT_ID,
        relative_path="Notes/cve.md",
        content="Patch notes for CVE-2026-9999.",
        revision=1,
        modified_at=NOW,
    )
    _indexed_metadata(metadata, embedder)
    chunk = _chunk(text="Patch notes for CVE-2026-9999.")
    documents.save_indexed(document, (chunk,), NOW)
    lexical_hit = SearchHit(chunk=chunk, score=2.5, lexical_score=2.5)
    lexical = RecordingLexicalIndex((lexical_hit,))

    retrieval = RetrievalService(
        embedder=embedder,
        vector_index=vectors,
        document_repository=documents,
        index_metadata_store=metadata,
        active_fingerprint=_fingerprint(embedder),
        lexical_index=lexical,
        retrieval_mode="hybrid",
        hybrid_candidate_multiplier=2,
        top_k=10,
    )
    results = asyncio.run(retrieval.retrieve("CVE-2026-9999", limit=5))

    assert lexical.search_calls == 1
    assert len(results) == 1
    assert results[0].relative_path == RelativePath("Notes/cve.md")
    assert "CVE-2026-9999" in results[0].hit.chunk.text


def test_reranker_expands_candidate_pool_before_final_limit() -> None:
    embedder = FakeEmbedder()
    documents = FakeDocumentRepository()
    vectors = FakeVectorIndex()
    metadata = FakeIndexMetadataStore()
    _indexed_metadata(metadata, embedder)
    chunks = tuple(_chunk(text=f"chunk-{index}", index=index) for index in range(3))
    document = Document.create(
        id=DocumentId("document-01"),
        vault_id=VAULT_ID,
        relative_path="Notes/Many.md",
        content=" ".join(chunk.text for chunk in chunks),
        revision=1,
        modified_at=NOW,
    )
    documents.save_indexed(document, chunks, NOW)
    vectors.upsert(document, chunks, embedder.embed_documents(chunks))
    reranker = FakeReranker()
    retrieval = RetrievalService(
        embedder=embedder,
        vector_index=vectors,
        document_repository=documents,
        index_metadata_store=metadata,
        active_fingerprint=_fingerprint(embedder),
        reranker=reranker,
        rerank_candidate_limit=3,
    )
    results = asyncio.run(retrieval.retrieve("chunk", limit=1))
    assert len(results) == 1
    assert reranker.last_query == "chunk"


def test_hybrid_mode_requires_lexical_index() -> None:
    from domain.errors import AdapterNotConfiguredError

    with pytest.raises(AdapterNotConfiguredError, match="lexical_index"):
        RetrievalService(
            embedder=FakeEmbedder(),
            vector_index=FakeVectorIndex(),
            document_repository=FakeDocumentRepository(),
            index_metadata_store=FakeIndexMetadataStore(),
            active_fingerprint=_fingerprint(FakeEmbedder()),
            retrieval_mode="hybrid",
        )
