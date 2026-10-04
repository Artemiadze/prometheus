"""Integration tests for hybrid retrieval via Container."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.outbound.filesystem.data_dir import ensure_layout
from bootstrap.config import RetrievalMode, RuntimeSettings
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


def _container(tmp_path: Path, *, retrieval_mode: RetrievalMode) -> Container:
    return Container(
        RuntimeSettings(data_dir=tmp_path, retrieval_mode=retrieval_mode),
        ensure_layout(tmp_path),
        vault_id=VaultId("hybrid-vault"),
        embedder_factory=FakeEmbedder,
        language_model_factory=FakeLanguageModel,
        markdown_parser_factory=FakeMarkdownParser,
        chunker_factory=FakeChunker,
        token_counter_factory=FakeTokenCounter,
    )


def test_hybrid_search_finds_lexical_token(tmp_path: Path) -> None:
    vault_id = VaultId("hybrid-vault")
    container = _container(tmp_path, retrieval_mode="hybrid")
    try:
        document = Document.create(
            id=DocumentId.from_relative_path("Notes/cve.md"),
            vault_id=vault_id,
            relative_path="Notes/cve.md",
            content="Patch notes for CVE-2026-HYBRID-1.",
            revision=1,
            modified_at=NOW,
        )
        asyncio.run(container.index_document.execute(document))
        hits = asyncio.run(
            container.search_notes.execute("CVE-2026-HYBRID-1", limit=5),
        )
        assert hits
        assert hits[0].relative_path.value == "Notes/cve.md"
    finally:
        container.close()


def test_dense_and_hybrid_both_return_cve_document(tmp_path: Path) -> None:
    vault_id = VaultId("hybrid-vault")
    content = "Details for CVE-2026-HYBRID-2 in production."

    def index_with(mode: RetrievalMode) -> tuple[int, ...]:
        container = _container(tmp_path / mode, retrieval_mode=mode)
        try:
            document = Document.create(
                id=DocumentId.from_relative_path("Notes/prod.md"),
                vault_id=vault_id,
                relative_path="Notes/prod.md",
                content=content,
                revision=1,
                modified_at=NOW,
            )
            asyncio.run(container.index_document.execute(document))
            hits = asyncio.run(
                container.search_notes.execute("CVE-2026-HYBRID-2", limit=5),
            )
            return tuple(1 for _ in hits if "CVE-2026-HYBRID-2" in _.text)
        finally:
            container.close()

    dense_matches = index_with("dense")
    hybrid_matches = index_with("hybrid")
    assert sum(dense_matches) >= 1
    assert sum(hybrid_matches) >= 1
