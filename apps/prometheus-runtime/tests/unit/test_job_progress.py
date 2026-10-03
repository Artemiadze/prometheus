"""Tests for reindex progress reporting cadence."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from application.dto.index_fingerprint import IndexFingerprint
from application.dto.indexing import IndexDocumentResult
from application.use_cases.reindex_vault import ReindexVault, _should_report_progress
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId
from fakes.fake_embedder import FakeEmbedder
from fakes.fake_index_metadata_store import FakeIndexMetadataStore
from fakes.fake_job_store import FakeJobStore
from fakes.fake_progress_reporter import FakeProgressReporter
from fakes.fake_unit_of_work import FakeUnitOfWork
from fakes.fake_vector_index import FakeVectorIndex

NOW = datetime(2026, 1, 1, tzinfo=UTC)
VAULT = VaultId("vault-01")


def test_should_report_on_interval_and_last_document() -> None:
    assert _should_report_progress(10, 100, 10)
    assert _should_report_progress(99, 100, 10) is False
    assert _should_report_progress(100, 100, 10)


def test_reindex_reports_progress_every_n_documents() -> None:
    class CountingIndex:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, document: Document, *, force: bool = False) -> IndexDocumentResult:
            self.calls += 1
            return IndexDocumentResult(document.id, 1, 0)

    documents = tuple(
        Document.create(
            id=DocumentId(f"document-{index:02d}"),
            vault_id=VAULT,
            relative_path=f"Notes/{index}.md",
            content=f"# Note {index}",
            revision=1,
            modified_at=NOW,
        )
        for index in range(25)
    )
    jobs = FakeJobStore()
    reporter = FakeProgressReporter()
    embedder = FakeEmbedder()
    index = CountingIndex()
    metadata = FakeIndexMetadataStore()

    class Workspace:
        def begin(self) -> object:
            return SimpleNamespace(
                index_document=index,
                document_repository=SimpleNamespace(),
                vector_index=FakeVectorIndex(),
                index_metadata_store=metadata,
                unit_of_work=FakeUnitOfWork(),
                promote=lambda: None,
                discard=lambda: None,
            )

    use_case = ReindexVault(
        vault_id=VAULT,
        rebuild_workspace=Workspace(),  # type: ignore[arg-type]
        active_fingerprint=IndexFingerprint(
            embedding=embedder.fingerprint,
            parser_version=1,
            chunker_version=1,
            payload_schema_version=2,
            chunk_size=700,
            chunk_overlap=80,
        ),
        job_store=jobs,
        progress_reporter=reporter,
        progress_interval=10,
    )

    class Token:
        def is_cancelled(self) -> bool:
            return False

    asyncio.run(use_case.execute(documents, cancellation=Token(), job=None))
    reported = [progress.processed_documents for _, progress in reporter.updates]
    assert 10 in reported
    assert 20 in reported
    assert reported[-1] == 25
