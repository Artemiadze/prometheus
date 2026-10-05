"""Integration tests for lexical index via Container (PRM-89)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.outbound.filesystem.data_dir import ensure_layout
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
    vault_id = VaultId("lexical-vault")
    return Container(
        RuntimeSettings(data_dir=tmp_path),
        ensure_layout(tmp_path),
        vault_id=vault_id,
        embedder_factory=FakeEmbedder,
        language_model_factory=FakeLanguageModel,
        markdown_parser_factory=FakeMarkdownParser,
        chunker_factory=FakeChunker,
        token_counter_factory=FakeTokenCounter,
    )


def test_container_indexes_and_lexical_search_finds_cve(tmp_path: Path) -> None:
    vault_id = VaultId("lexical-vault")
    container = _container(tmp_path)
    try:
        document = Document.create(
            id=DocumentId.from_relative_path("Notes/cve.md"),
            vault_id=vault_id,
            relative_path="Notes/cve.md",
            content="Patch notes for CVE-2026-1234.",
            revision=1,
            modified_at=NOW,
        )
        asyncio.run(container.index_document.execute(document))
        hits = container.lexical_index.search("CVE-2026-1234", limit=5)
        assert hits
        assert hits[0].lexical_score is not None
    finally:
        container.close()


def test_remove_document_clears_lexical_rows(tmp_path: Path) -> None:
    vault_id = VaultId("lexical-vault")
    container = _container(tmp_path)
    try:
        document = Document.create(
            id=DocumentId.from_relative_path("Notes/remove.md"),
            vault_id=vault_id,
            relative_path="Notes/remove.md",
            content="token REMOVELEX-001",
            revision=1,
            modified_at=NOW,
        )
        asyncio.run(container.index_document.execute(document))
        assert container.lexical_index.search("REMOVELEX-001", limit=5)
        asyncio.run(container.remove_document.execute(document.id))
        assert container.lexical_index.search("REMOVELEX-001", limit=5) == ()
    finally:
        container.close()
