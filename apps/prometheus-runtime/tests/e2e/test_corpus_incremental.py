"""E2E corpus: index → search → answer with incremental update (PRM-83)."""

from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.outbound.filesystem.data_dir import ensure_layout
from adapters.outbound.network.guard import NetworkGuard
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from domain.entities.document import Document
from domain.errors import ConfigurationError
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId
from fakes import FakeChunker, FakeEmbedder, FakeLanguageModel, FakeMarkdownParser, FakeTokenCounter

pytestmark = pytest.mark.e2e

NOW = datetime(2026, 1, 1, tzinfo=UTC)
CORPUS = Path(__file__).resolve().parent / "fixtures" / "corpus"


def _load_corpus() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8").strip() for path in sorted(CORPUS.glob("*.md"))
    }


def test_corpus_index_search_answer_and_incremental_update(tmp_path: Path) -> None:
    vault_id = VaultId("corpus-vault")
    embedder = FakeEmbedder()
    language_model = FakeLanguageModel()
    container = Container(
        RuntimeSettings(data_dir=tmp_path),
        ensure_layout(tmp_path),
        vault_id=vault_id,
        embedder_factory=lambda: embedder,
        language_model_factory=lambda: language_model,
        markdown_parser_factory=FakeMarkdownParser,
        chunker_factory=FakeChunker,
        token_counter_factory=FakeTokenCounter,
    )
    notes = _load_corpus()
    documents = {
        name: Document.create(
            id=DocumentId.from_relative_path(f"Notes/{name}"),
            vault_id=vault_id,
            relative_path=f"Notes/{name}",
            content=content,
            revision=1,
            modified_at=NOW,
        )
        for name, content in notes.items()
    }

    with NetworkGuard():
        for document in documents.values():
            asyncio.run(container.index_document.execute(document))

        alpha = documents["alpha.md"]
        alpha_hits = asyncio.run(container.search_notes.execute(alpha.content, limit=5))
        answer = asyncio.run(container.answer_question.execute(alpha.content, limit=5))

        with pytest.raises(ConfigurationError, match="target localhost"):
            socket.create_connection(("8.8.8.8", 53))

        updated_content = (
            "# Alpha Note\n\nUnique token: alphaincrementalmarker\n\nUpdated alpha body."
        )
        updated = Document.create(
            id=alpha.id,
            vault_id=vault_id,
            relative_path="Notes/alpha.md",
            content=updated_content,
            revision=2,
            modified_at=NOW,
        )
        asyncio.run(container.index_document.execute(updated))
        new_hits = asyncio.run(container.search_notes.execute(updated_content, limit=5))
        stale_hits = asyncio.run(container.search_notes.execute(alpha.content, limit=5))

    assert alpha_hits
    assert alpha_hits[0].relative_path.value == "Notes/alpha.md"
    assert "alphacorpusmarker" in alpha_hits[0].text
    assert answer.insufficient_context is False
    assert answer.sources
    assert any(source.relative_path.value == "Notes/alpha.md" for source in answer.sources)
    assert language_model.calls
    assert new_hits
    assert "alphaincrementalmarker" in new_hits[0].text
    assert new_hits[0].relative_path.value == "Notes/alpha.md"
    # Old alpha body is no longer the best match for the previous full-document query.
    assert not any("alphacorpusmarker" in hit.text for hit in stale_hits[:1]) or (
        stale_hits[0].relative_path.value != "Notes/alpha.md"
    )
    container.close()
