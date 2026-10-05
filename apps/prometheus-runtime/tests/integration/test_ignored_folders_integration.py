"""Integration tests for ignored folders in indexing and retrieval."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.outbound.filesystem.data_dir import ensure_layout
from application.errors import PathIgnoredError
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId
from fakes import (
    FakeChunker,
    FakeEmbedder,
    FakeLanguageModel,
    FakeMarkdownParser,
    FakeTokenCounter,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _container(tmp_path: Path) -> Container:
    return Container(
        RuntimeSettings(data_dir=tmp_path),
        ensure_layout(tmp_path),
        vault_id=VaultId("ignored-vault"),
        embedder_factory=FakeEmbedder,
        language_model_factory=FakeLanguageModel,
        markdown_parser_factory=FakeMarkdownParser,
        chunker_factory=FakeChunker,
        token_counter_factory=FakeTokenCounter,
    )


def test_index_rejects_ignored_path(tmp_path: Path) -> None:
    container = _container(tmp_path)
    try:
        asyncio.run(
            container.update_ignored_folders.execute(["Templates/"]),
        )
        document = Document.create(
            id=DocumentId.from_relative_path("Templates/x.md"),
            vault_id=VaultId("ignored-vault"),
            relative_path="Templates/x.md",
            content="ignored content",
            revision=1,
            modified_at=NOW,
        )
        with pytest.raises(PathIgnoredError):
            asyncio.run(container.index_document.execute(document))
    finally:
        container.close()


def test_ignored_folder_excluded_from_search(tmp_path: Path) -> None:
    vault_id = VaultId("ignored-vault")
    container = _container(tmp_path)
    try:
        note = Document.create(
            id=DocumentId.from_relative_path("Notes/visible.md"),
            vault_id=vault_id,
            relative_path="Notes/visible.md",
            content="VISIBLE-TOKEN-123",
            revision=1,
            modified_at=NOW,
        )
        hidden = Document.create(
            id=DocumentId.from_relative_path("Archive/hidden.md"),
            vault_id=vault_id,
            relative_path="Archive/hidden.md",
            content="VISIBLE-TOKEN-123",
            revision=1,
            modified_at=NOW,
        )
        asyncio.run(container.index_document.execute(note))
        asyncio.run(container.index_document.execute(hidden))
        asyncio.run(container.update_ignored_folders.execute(["Archive/"]))
        hits = asyncio.run(container.search_notes.execute("VISIBLE-TOKEN-123", limit=5))
        paths = {hit.relative_path.value for hit in hits}
        assert paths == {"Notes/visible.md"}
    finally:
        container.close()
