"""Integration coverage for storage and retrieval isolation between Vaults."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from adapters.outbound.filesystem.data_dir import ensure_layout
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId
from fakes import FakeChunker, FakeEmbedder, FakeMarkdownParser

NOW = datetime(2026, 1, 1, tzinfo=UTC)
DOCUMENT_ID = DocumentId("same-document-id")


def _container(tmp_path: Path, vault_id: VaultId, embedder: FakeEmbedder) -> Container:
    return Container(
        RuntimeSettings(data_dir=tmp_path),
        ensure_layout(tmp_path),
        vault_id=vault_id,
        embedder_factory=lambda: embedder,
        markdown_parser_factory=FakeMarkdownParser,
        chunker_factory=FakeChunker,
    )


def _document(vault_id: VaultId, content: str) -> Document:
    return Document.create(
        id=DOCUMENT_ID,
        vault_id=vault_id,
        relative_path="Notes/Private.md",
        content=content,
        revision=1,
        modified_at=NOW,
    )


def test_search_results_do_not_cross_vault_boundaries(tmp_path: Path) -> None:
    vault_a_id = VaultId("vault-a")
    vault_b_id = VaultId("vault-b")
    vault_a = _container(tmp_path, vault_a_id, FakeEmbedder())
    vault_b = _container(tmp_path, vault_b_id, FakeEmbedder())

    asyncio.run(vault_a.index_document.execute(_document(vault_a_id, "alpha secret")))
    asyncio.run(vault_b.index_document.execute(_document(vault_b_id, "bravo secret")))

    results_a = asyncio.run(vault_a.search_notes.execute("alpha", limit=10))
    results_b = asyncio.run(vault_b.search_notes.execute("bravo", limit=10))

    assert [result.text for result in results_a] == ["alpha secret"]
    assert [result.text for result in results_b] == ["bravo secret"]

    vault_a.close()
    vault_b.close()
