"""Offline index-to-answer scenario with external networking blocked."""

from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from adapters.inbound.http.app import create_app
from adapters.outbound.filesystem.data_dir import ensure_layout
from adapters.outbound.network.guard import NetworkGuard
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from bootstrap.container_registry import VaultContainerRegistry
from domain.entities.document import Document
from domain.errors import ConfigurationError
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId
from fakes import (
    FakeChunker,
    FakeEmbedder,
    FakeLanguageModel,
    FakeMarkdownParser,
    FakeTokenCounter,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_index_search_and_answer_work_while_external_network_is_blocked(
    tmp_path: Path,
) -> None:
    vault_id = VaultId("offline-vault")
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
    document = Document.create(
        id=DocumentId("offline-document"),
        vault_id=vault_id,
        relative_path="Notes/Offline.md",
        content="local offline retrieval answer",
        revision=1,
        modified_at=NOW,
    )

    with NetworkGuard():
        asyncio.run(container.index_document.execute(document))
        results = asyncio.run(
            container.search_notes.execute(document.content, limit=10)
        )
        answer = asyncio.run(
            container.answer_question.execute(document.content, limit=10)
        )

        with pytest.raises(ConfigurationError, match="target localhost"):
            socket.create_connection(("8.8.8.8", 53))

    assert [result.text for result in results] == [document.content]
    assert answer.insufficient_context is False
    assert language_model.calls
    container.close()


def test_http_index_search_chat_work_while_external_network_is_blocked(
    tmp_path: Path,
) -> None:
    layout = ensure_layout(tmp_path)
    settings = RuntimeSettings(
        data_dir=tmp_path, session_token=SecretStr("offline-token")
    )
    base = Container(
        settings,
        layout,
        embedder_factory=FakeEmbedder,
        language_model_factory=FakeLanguageModel,
        markdown_parser_factory=FakeMarkdownParser,
        chunker_factory=FakeChunker,
        token_counter_factory=FakeTokenCounter,
    )
    registry = VaultContainerRegistry(base)
    client = TestClient(
        create_app(base, vault_registry=registry, job_store=base.job_store),
        base_url="http://127.0.0.1:8765",
    )
    headers = {
        "Authorization": "Bearer offline-token",
        "X-Prometheus-Plugin-Version": "0.1.0",
    }
    vault = "offline-vault"
    document_id = "offline-document"

    with NetworkGuard():
        put = client.put(
            f"/v1/vaults/{vault}/documents/{document_id}",
            json={
                "path": "Notes/Offline.md",
                "content": "local offline retrieval answer",
                "revision": 1,
                "modified_at": NOW.isoformat(),
            },
            headers=headers,
        )
        search = client.post(
            f"/v1/vaults/{vault}/search",
            json={"query": "local offline retrieval answer"},
            headers=headers,
        )
        chat = client.post(
            f"/v1/vaults/{vault}/chat",
            json={"query": "local offline retrieval answer"},
            headers=headers,
        )
        with pytest.raises(ConfigurationError, match="target localhost"):
            socket.create_connection(("8.8.8.8", 53))

    assert put.status_code == 200
    assert search.status_code == 200
    assert chat.status_code == 200
    assert [item["text"] for item in search.json()["results"]] == [
        "local offline retrieval answer"
    ]
    assert chat.json()["insufficient_context"] is False
    assert chat.json()["answer"]
    registry.close_all()
    base.close()
