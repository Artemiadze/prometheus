"""Acceptance-level unit tests for PRM-E9 use cases."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from application.dto.index_fingerprint import IndexFingerprint
from application.dto.runtime_status import IndexState
from application.dto.statistics import IndexStatistics
from application.dto.vault_sync import VaultSnapshot, VaultSnapshotEntry
from application.errors import QueryTooShortError
from application.services.retrieval import RetrievalService
from application.use_cases.answer_question import AnswerQuestion
from application.use_cases.get_runtime_status import GetRuntimeStatus
from application.use_cases.index_document import IndexDocument
from application.use_cases.reindex_vault import ReindexVault
from application.use_cases.remove_document import RemoveDocument
from application.use_cases.rename_document import RenameDocument
from application.use_cases.search_notes import SearchNotes
from application.use_cases.synchronize_vault import SynchronizeVault
from domain.entities.document import Document
from domain.services.grounding_policy import GroundingPolicy
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import SearchScope
from domain.value_objects.vault_id import VaultId
from fakes import (
    FakeChunker,
    FakeDocumentRepository,
    FakeEmbedder,
    FakeIndexMetadataStore,
    FakeIndexStatisticsReader,
    FakeJobStore,
    FakeLanguageModel,
    FakeMarkdownParser,
    FakeProgressReporter,
    FakeTokenCounter,
    FakeUnitOfWork,
    FakeVectorIndex,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
VAULT_ID = VaultId("vault-01")


def _document(path: str = "Notes/One.md", *, revision: int = 1) -> Document:
    return Document.create(
        id=DocumentId("document-01"),
        vault_id=VAULT_ID,
        relative_path=path,
        content="semantic retrieval content",
        revision=revision,
        modified_at=NOW,
    )


def _fingerprint(embedder: FakeEmbedder) -> IndexFingerprint:
    return IndexFingerprint(embedder.fingerprint, 1, 1, 1, 700, 80)


def _indexing_setup() -> tuple[
    IndexDocument,
    RemoveDocument,
    RenameDocument,
    FakeEmbedder,
    FakeDocumentRepository,
    FakeVectorIndex,
    FakeIndexMetadataStore,
]:
    embedder = FakeEmbedder()
    documents = FakeDocumentRepository()
    vectors = FakeVectorIndex()
    metadata = FakeIndexMetadataStore()
    unit_of_work = FakeUnitOfWork()
    rename = RenameDocument(
        document_repository=documents,
        vector_index=vectors,
        unit_of_work=unit_of_work,
    )
    index = IndexDocument(
        vault_id=VAULT_ID,
        parser=FakeMarkdownParser(),
        chunker=FakeChunker(),
        embedder=embedder,
        vector_index=vectors,
        document_repository=documents,
        unit_of_work=unit_of_work,
        index_metadata_store=metadata,
        active_fingerprint=_fingerprint(embedder),
        rename_document=rename,
        max_document_chars=2_000_000,
        max_chunks_per_document=10_000,
        clock=lambda: NOW,
    )
    remove = RemoveDocument(
        document_repository=documents,
        vector_index=vectors,
        unit_of_work=unit_of_work,
    )
    return index, remove, rename, embedder, documents, vectors, metadata


def test_index_is_idempotent_and_rename_updates_scope_without_embedding() -> None:
    index, _, _, embedder, _, vectors, _ = _indexing_setup()
    document = _document()
    first = asyncio.run(index.execute(document))
    second = asyncio.run(index.execute(document))
    renamed = asyncio.run(index.execute(_document("Archive/One.md", revision=2)))

    assert first.created_chunks == 1
    assert second.skipped
    assert renamed.relocated
    assert embedder.document_calls == 1
    hits = vectors.search(
        embedder.embed_query(document.content),
        10,
        SearchScope.current_folder("Archive"),
    )
    assert len(hits) == 1


def test_remove_is_idempotent_and_removes_search_hits() -> None:
    index, remove, _, embedder, _, vectors, _ = _indexing_setup()
    document = _document()
    asyncio.run(index.execute(document))

    first = asyncio.run(remove.execute(document.id))
    second = asyncio.run(remove.execute(document.id))

    assert first.removed and first.removed_chunks == 1
    assert not second.removed
    assert vectors.search(embedder.embed_query(document.content), 10) == ()


def test_synchronize_classifies_snapshot_and_removes_missing_documents() -> None:
    index, remove, rename, _, documents, _, _ = _indexing_setup()
    document = _document()
    asyncio.run(index.execute(document))
    synchronize = SynchronizeVault(
        document_repository=documents,
        remove_document=remove,
        rename_document=rename,
    )
    added = VaultSnapshotEntry(
        DocumentId("document-02"),
        RelativePath("Two.md"),
        "a" * 64,
        1,
        NOW,
    )

    summary = asyncio.run(synchronize.execute(VaultSnapshot((added,))))

    assert summary.added == (added,)
    assert summary.deleted == (document.id,)
    assert documents.get_state(document.id) is None


def test_search_rejects_short_query_and_never_needs_language_model() -> None:
    index, _, _, _, documents, vectors, metadata = _indexing_setup()
    asyncio.run(index.execute(_document()))
    retrieval = RetrievalService(
        embedder=FakeEmbedder(),
        vector_index=vectors,
        document_repository=documents,
        index_metadata_store=metadata,
    )
    search = SearchNotes(retrieval)

    with pytest.raises(QueryTooShortError):
        asyncio.run(search.execute(" ", limit=10))
    results = asyncio.run(search.execute("semantic", limit=10))

    assert results[0].relative_path == RelativePath("Notes/One.md")
    assert results[0].text == "semantic retrieval content"


def test_answer_skips_llm_for_insufficient_context_and_uses_prompt_sources() -> None:
    index, _, _, _, documents, vectors, metadata = _indexing_setup()
    asyncio.run(index.execute(_document()))
    retrieval = RetrievalService(
        embedder=FakeEmbedder(),
        vector_index=vectors,
        document_repository=documents,
        index_metadata_store=metadata,
    )
    llm = FakeLanguageModel()
    insufficient = AnswerQuestion(
        retrieval=retrieval,
        grounding_policy=GroundingPolicy(min_score=2.0),
        token_counter=FakeTokenCounter(),
        language_model=llm,
        context_size=1024,
        response_token_reserve=128,
        temperature=0.1,
    )
    grounded = AnswerQuestion(
        retrieval=retrieval,
        grounding_policy=GroundingPolicy(min_score=-1.0),
        token_counter=FakeTokenCounter(),
        language_model=llm,
        context_size=1024,
        response_token_reserve=128,
        temperature=0.1,
    )

    missing = asyncio.run(insufficient.execute("semantic question", limit=10))
    answer = asyncio.run(grounded.execute("semantic question", limit=10))

    assert missing.insufficient_context and len(llm.calls) == 1
    assert not answer.insufficient_context
    assert answer.sources[0].relative_path == RelativePath("Notes/One.md")
    assert len(answer.used_chunk_ids) == 1


class _Cancelled:
    def is_cancelled(self) -> bool:
        return True


def test_reindex_cancellation_keeps_manifest_consistent() -> None:
    index, remove, _, embedder, documents, _, metadata = _indexing_setup()
    asyncio.run(index.execute(_document()))
    jobs = FakeJobStore()
    reindex = ReindexVault(
        index_document=index,
        remove_document=remove,
        document_repository=documents,
        index_metadata_store=metadata,
        active_fingerprint=_fingerprint(embedder),
        job_store=jobs,
        progress_reporter=FakeProgressReporter(),
    )

    result = asyncio.run(reindex.execute((_document(),), cancellation=_Cancelled()))

    assert result.cancelled
    assert documents.list_states() == ()


class _UnavailableLanguageModel(FakeLanguageModel):
    async def is_available(self) -> bool:
        raise RuntimeError("offline")


def test_runtime_status_is_not_indexed_and_tolerates_ollama_failure() -> None:
    _, _, _, embedder, _, vectors, metadata = _indexing_setup()
    status = GetRuntimeStatus(
        runtime_version="0.1.0",
        llm_model="qwen3:4b",
        language_model=_UnavailableLanguageModel(),
        vector_index=vectors,
        index_metadata_store=metadata,
        index_statistics=FakeIndexStatisticsReader(IndexStatistics(0, 0, None, 0)),
        active_fingerprint=_fingerprint(embedder),
    )

    result = asyncio.run(status.execute())

    assert result.index_state is IndexState.NOT_INDEXED
    assert not result.llm_available
