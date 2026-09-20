"""Integration coverage for atomic side-by-side index rebuilds."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from adapters.outbound.filesystem.data_dir import ensure_layout, vault_dir
from adapters.outbound.filesystem.index_rebuild import REBUILD_DIRNAME
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId
from fakes import FakeChunker, FakeEmbedder, FakeJobStore, FakeMarkdownParser, FakeProgressReporter

NOW = datetime(2026, 1, 1, tzinfo=UTC)
VAULT = VaultId("vault-rebuild")


class _NeverCancelled:
    def is_cancelled(self) -> bool:
        return False


class _CancelAfterFirst:
    def __init__(self) -> None:
        self.checks = 0

    def is_cancelled(self) -> bool:
        self.checks += 1
        return self.checks > 1


def _container(tmp_path: Path) -> Container:
    jobs = FakeJobStore()
    return Container(
        RuntimeSettings(data_dir=tmp_path),
        ensure_layout(tmp_path),
        vault_id=VAULT,
        embedder_factory=FakeEmbedder,
        markdown_parser_factory=FakeMarkdownParser,
        chunker_factory=FakeChunker,
        job_store_factory=lambda: jobs,
        progress_reporter_factory=FakeProgressReporter,
    )


def _document(document_id: str, content: str) -> Document:
    return Document.create(
        id=DocumentId(document_id),
        vault_id=VAULT,
        relative_path=f"Notes/{document_id}.md",
        content=content,
        revision=1,
        modified_at=NOW,
    )


def test_search_continues_on_active_index_until_promote(tmp_path: Path) -> None:
    container = _container(tmp_path)
    original = _document("document-a", "original alpha content")
    asyncio.run(container.index_document.execute(original))

    results_before = asyncio.run(container.search_notes.execute("original", limit=5))
    assert [result.text for result in results_before] == ["original alpha content"]

    replacement = _document("document-b", "replacement bravo content")
    result = asyncio.run(
        container.reindex_vault.execute((replacement,), cancellation=_NeverCancelled())
    )

    assert not result.cancelled
    vault_path = vault_dir(container.layout, VAULT.value)
    assert not (vault_path / REBUILD_DIRNAME).exists()
    assert not (vault_path / ".previous").exists()

    results_after = asyncio.run(container.search_notes.execute("replacement", limit=5))
    assert [result.text for result in results_after] == ["replacement bravo content"]
    container.close()


def test_cancelled_rebuild_leaves_active_index_intact(tmp_path: Path) -> None:
    container = _container(tmp_path)
    original = _document("document-a", "stable vault content")
    asyncio.run(container.index_document.execute(original))

    result = asyncio.run(
        container.reindex_vault.execute(
            (
                _document("document-b", "partial staging"),
                _document("document-c", "should not finish"),
            ),
            cancellation=_CancelAfterFirst(),
        )
    )

    assert result.cancelled
    vault_path = vault_dir(container.layout, VAULT.value)
    assert not (vault_path / REBUILD_DIRNAME).exists()
    results = asyncio.run(container.search_notes.execute("stable", limit=5))
    assert [result.text for result in results] == ["stable vault content"]
    container.close()
