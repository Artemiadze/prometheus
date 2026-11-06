"""Integration coverage for atomic side-by-side index rebuilds."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from adapters.outbound.filesystem.data_dir import ensure_layout, vault_dir
from adapters.outbound.filesystem.index_rebuild import (
    PREVIOUS_DIRNAME,
    PROMOTE_MARKER,
    REBUILD_DIRNAME,
    recover_interrupted_promotion,
)
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId
from fakes import (
    FakeChunker,
    FakeEmbedder,
    FakeJobStore,
    FakeMarkdownParser,
    FakeProgressReporter,
)

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
    assert not (vault_path / PREVIOUS_DIRNAME).exists()
    assert not (vault_path / PROMOTE_MARKER).exists()

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


def test_reindex_skips_oversized_document_and_indexes_the_rest(tmp_path: Path) -> None:
    jobs = FakeJobStore()
    container = Container(
        RuntimeSettings(data_dir=tmp_path, max_document_chars=40),
        ensure_layout(tmp_path),
        vault_id=VAULT,
        embedder_factory=FakeEmbedder,
        markdown_parser_factory=FakeMarkdownParser,
        chunker_factory=FakeChunker,
        job_store_factory=lambda: jobs,
        progress_reporter_factory=FakeProgressReporter,
    )

    result = asyncio.run(
        container.reindex_vault.execute(
            (
                _document("document-big", "x" * 200),
                _document("document-ok", "small searchable bravo"),
            ),
            cancellation=_NeverCancelled(),
        )
    )

    assert not result.cancelled
    assert result.job.status.value == "completed"
    assert result.processed_documents == 2
    found = asyncio.run(container.search_notes.execute("bravo", limit=5))
    assert [hit.text for hit in found] == ["small searchable bravo"]
    container.close()


def test_failed_rebuild_discards_staging_and_keeps_active_searchable(
    tmp_path: Path,
) -> None:
    import pytest

    from application.errors import VaultMismatchError

    container = _container(tmp_path)
    original = _document("document-a", "stable vault content")
    asyncio.run(container.index_document.execute(original))
    foreign = Document.create(
        id=DocumentId("document-b"),
        vault_id=VaultId("other-vault"),
        relative_path="Notes/document-b.md",
        content="should not replace active",
        revision=1,
        modified_at=NOW,
    )

    with pytest.raises(VaultMismatchError):
        asyncio.run(container.reindex_vault.execute((foreign,), cancellation=_NeverCancelled()))

    vault_path = vault_dir(container.layout, VAULT.value)
    assert not (vault_path / REBUILD_DIRNAME).exists()
    results = asyncio.run(container.search_notes.execute("stable", limit=5))
    assert [result.text for result in results] == ["stable vault content"]
    container.close()


def test_crash_after_moving_active_to_previous_is_recoverable(tmp_path: Path) -> None:
    container = _container(tmp_path)
    original = _document("document-a", "stable vault content")
    asyncio.run(container.index_document.execute(original))
    container.close()

    vault_path = vault_dir(ensure_layout(tmp_path), VAULT.value)
    previous = vault_path / PREVIOUS_DIRNAME
    previous.mkdir(mode=0o700)
    for name in ("metadata.sqlite",):
        source = vault_path / name
        if source.exists():
            source.rename(previous / name)
    (vault_path / PROMOTE_MARKER).write_text("previous", encoding="utf-8")
    (vault_path / REBUILD_DIRNAME).mkdir(mode=0o700)

    action = recover_interrupted_promotion(vault_path)

    assert action == "restored-previous"
    assert (vault_path / "metadata.sqlite").exists()
    assert not previous.exists()
    assert not (vault_path / PROMOTE_MARKER).exists()

    recovered = _container(tmp_path)
    results = asyncio.run(recovered.search_notes.execute("stable", limit=5))
    assert [result.text for result in results] == ["stable vault content"]
    recovered.close()


def test_crash_after_switching_active_finalizes_and_cleans_temp(tmp_path: Path) -> None:
    container = _container(tmp_path)
    original = _document("document-a", "original alpha content")
    asyncio.run(container.index_document.execute(original))
    replacement = _document("document-b", "replacement bravo content")
    asyncio.run(container.reindex_vault.execute((replacement,), cancellation=_NeverCancelled()))
    container.close()

    vault_path = vault_dir(ensure_layout(tmp_path), VAULT.value)
    previous = vault_path / PREVIOUS_DIRNAME
    previous.mkdir(mode=0o700)
    (previous / "metadata.sqlite").write_text("stale", encoding="utf-8")
    (vault_path / REBUILD_DIRNAME).mkdir(mode=0o700)
    (vault_path / PROMOTE_MARKER).write_text("active", encoding="utf-8")

    action = recover_interrupted_promotion(vault_path)

    assert action == "finalized-active"
    assert not previous.exists()
    assert not (vault_path / REBUILD_DIRNAME).exists()
    assert not (vault_path / PROMOTE_MARKER).exists()

    recovered = _container(tmp_path)
    results = asyncio.run(recovered.search_notes.execute("replacement", limit=5))
    assert [result.text for result in results] == ["replacement bravo content"]
    recovered.close()
