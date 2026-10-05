"""Tests for lazy composition-root providers."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from adapters.inbound.http.app import create_app
from adapters.outbound.fastembed.adapter import FastEmbedAdapter
from adapters.outbound.fastembed.reranker import FastEmbedReranker
from adapters.outbound.filesystem.data_dir import ensure_layout
from adapters.outbound.ollama.adapter import OllamaLanguageModel
from adapters.outbound.qdrant.adapter import QdrantLocalVectorIndex
from adapters.outbound.sqlite.document_repository import SqliteDocumentRepository
from application.ports.embedder import Embedder
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from domain.entities.document import Document
from domain.errors import AdapterNotConfiguredError
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId


def test_health_does_not_initialize_embedder(tmp_path: Path) -> None:
    calls = 0

    def build_embedder() -> Embedder:
        nonlocal calls
        calls += 1
        return cast(Embedder, object())

    container = Container(
        RuntimeSettings(data_dir=tmp_path),
        ensure_layout(tmp_path),
        embedder_factory=build_embedder,
    )

    response = TestClient(create_app(container), base_url="http://127.0.0.1:8765").get("/v1/health")

    assert response.status_code == 200
    assert calls == 0


def test_provider_is_initialized_once(tmp_path: Path) -> None:
    dependency = cast(Embedder, object())
    calls = 0

    def build_embedder() -> Embedder:
        nonlocal calls
        calls += 1
        return dependency

    container = Container(
        RuntimeSettings(data_dir=tmp_path),
        ensure_layout(tmp_path),
        embedder_factory=build_embedder,
    )

    assert container.embedder is dependency
    assert container.embedder is dependency
    assert calls == 1


def test_unconfigured_provider_has_explicit_error(tmp_path: Path) -> None:
    container = Container(RuntimeSettings(data_dir=tmp_path), ensure_layout(tmp_path))

    with pytest.raises(AdapterNotConfiguredError, match="VectorIndex adapter is not configured"):
        _ = container.vector_index


def test_reranker_is_disabled_by_default(tmp_path: Path) -> None:
    container = Container(RuntimeSettings(data_dir=tmp_path), ensure_layout(tmp_path))

    assert container.reranker is None


def test_reranker_can_be_enabled_via_settings(tmp_path: Path) -> None:
    container = Container(
        RuntimeSettings(data_dir=tmp_path, reranker_enabled=True),
        ensure_layout(tmp_path),
    )

    assert isinstance(container.reranker, FastEmbedReranker)


def test_default_embedder_is_wired_without_loading_model(tmp_path: Path) -> None:
    container = Container(RuntimeSettings(data_dir=tmp_path), ensure_layout(tmp_path))

    embedder = container.embedder

    assert isinstance(embedder, FastEmbedAdapter)
    assert embedder.dimension == 1024


def test_default_language_model_is_wired_without_network_request(
    tmp_path: Path,
) -> None:
    container = Container(RuntimeSettings(data_dir=tmp_path), ensure_layout(tmp_path))

    language_model = container.language_model

    assert isinstance(language_model, OllamaLanguageModel)
    asyncio.run(language_model.aclose())


def test_default_vector_index_is_scoped_to_configured_vault(tmp_path: Path) -> None:
    container = Container(
        RuntimeSettings(data_dir=tmp_path),
        ensure_layout(tmp_path),
        vault_id=VaultId("vault-01"),
    )

    vector_index = container.vector_index

    assert isinstance(vector_index, QdrantLocalVectorIndex)
    assert (tmp_path / "vaults" / "vault-01" / "qdrant").is_dir()
    vector_index.close()


def test_default_document_repository_is_scoped_to_configured_vault(
    tmp_path: Path,
) -> None:
    container = Container(
        RuntimeSettings(data_dir=tmp_path),
        ensure_layout(tmp_path),
        vault_id=VaultId("vault-01"),
    )

    repository = container.document_repository

    assert isinstance(repository, SqliteDocumentRepository)
    assert (tmp_path / "vaults" / "vault-01" / "metadata.sqlite").exists()


def test_metadata_adapters_share_one_underlying_database(tmp_path: Path) -> None:
    container = Container(
        RuntimeSettings(data_dir=tmp_path),
        ensure_layout(tmp_path),
        vault_id=VaultId("vault-01"),
    )
    document = Document.create(
        id=DocumentId("document-01"),
        vault_id=VaultId("vault-01"),
        relative_path="Notes/One.md",
        content="Body",
        revision=1,
        modified_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    container.document_repository.save_indexed(document, (), datetime(2026, 1, 2, tzinfo=UTC))
    statistics = container.index_statistics.read()

    assert statistics.document_count == 1
    assert container.index_metadata_store.load() is None


def test_unconfigured_metadata_adapters_have_an_explicit_error(tmp_path: Path) -> None:
    container = Container(RuntimeSettings(data_dir=tmp_path), ensure_layout(tmp_path))

    with pytest.raises(AdapterNotConfiguredError, match="Metadata store adapter is not configured"):
        _ = container.document_repository

    with pytest.raises(AdapterNotConfiguredError, match="Metadata store adapter is not configured"):
        _ = container.unit_of_work


def test_active_index_fingerprint_excludes_llm_and_top_k_settings(
    tmp_path: Path,
) -> None:
    layout = ensure_layout(tmp_path)
    baseline = Container(RuntimeSettings(data_dir=tmp_path), layout).active_index_fingerprint
    changed = Container(
        RuntimeSettings(data_dir=tmp_path, llm_model="different-model", top_k=25),
        layout,
    ).active_index_fingerprint

    assert baseline == changed


def test_active_index_fingerprint_reflects_chunking_settings(tmp_path: Path) -> None:
    layout = ensure_layout(tmp_path)
    baseline = Container(RuntimeSettings(data_dir=tmp_path), layout).active_index_fingerprint
    changed = Container(
        RuntimeSettings(data_dir=tmp_path, chunk_size=500, chunk_overlap=50),
        layout,
    ).active_index_fingerprint

    assert baseline != changed
