"""Tests for serialized per-document indexing."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from application.dto.indexing import IndexDocumentResult
from application.services.document_indexing_queue import SerializedDocumentIndexing
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId

NOW = datetime(2026, 1, 1, tzinfo=UTC)
VAULT = VaultId("vault-01")
DOC = DocumentId("document-01")


def _document(*, content: str, revision: int) -> Document:
    return Document.create(
        id=DOC,
        vault_id=VAULT,
        relative_path="Notes/One.md",
        content=content,
        revision=revision,
        modified_at=NOW,
    )


def test_parallel_requests_keep_last_revision() -> None:
    indexed_revisions: list[int] = []

    class TrackingIndex:
        async def execute(self, document: Document, *, force: bool = False) -> object:
            await asyncio.sleep(0.01)
            indexed_revisions.append(document.revision)
            return IndexDocumentResult(document.id, 1, 0)

    queue = SerializedDocumentIndexing(TrackingIndex())  # type: ignore[arg-type]

    async def run() -> None:
        await asyncio.gather(
            queue.execute(_document(content="v1", revision=1)),
            queue.execute(_document(content="v2", revision=2)),
            queue.execute(_document(content="v3", revision=3)),
        )

    asyncio.run(run())
    assert indexed_revisions == [3]
    assert queue._inflight == {}
    assert queue._latest_revision == {}
    assert queue._indexed_revision == {}
    assert queue._pending == {}
    assert queue._locks == {}


def test_same_revision_after_prior_index_is_not_skipped() -> None:
    """Delete → recreate (or a fresh session) may re-send revision 1; must index."""

    indexed_contents: list[str] = []

    class TrackingIndex:
        async def execute(self, document: Document, *, force: bool = False) -> object:
            indexed_contents.append(document.content)
            return IndexDocumentResult(document.id, 1, 0)

    queue = SerializedDocumentIndexing(TrackingIndex())  # type: ignore[arg-type]

    async def run() -> None:
        first = await queue.execute(_document(content="original", revision=1))
        assert first.skipped is False
        assert queue._indexed_revision == {}
        second = await queue.execute(_document(content="recreated", revision=1))
        assert second.skipped is False

    asyncio.run(run())
    assert indexed_contents == ["original", "recreated"]
    assert queue._inflight == {}


def test_state_cleared_after_requests_finish() -> None:
    class TrackingIndex:
        async def execute(self, document: Document, *, force: bool = False) -> object:
            return IndexDocumentResult(document.id, 1, 0)

    queue = SerializedDocumentIndexing(TrackingIndex())  # type: ignore[arg-type]

    async def run() -> None:
        await queue.execute(_document(content="v1", revision=5))

    asyncio.run(run())
    assert queue._inflight == {}
    assert queue._latest_revision == {}
    assert queue._indexed_revision == {}
    assert queue._pending == {}
    assert queue._locks == {}
