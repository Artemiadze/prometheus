"""Tests for lazy composition-root providers."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from adapters.inbound.http.app import create_app
from adapters.outbound.fastembed.adapter import FastEmbedAdapter
from adapters.outbound.filesystem.data_dir import ensure_layout
from adapters.outbound.qdrant.adapter import QdrantLocalVectorIndex
from application.ports.embedder import Embedder
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from domain.errors import AdapterNotConfiguredError
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

    response = TestClient(create_app(container)).get("/v1/health")

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


def test_default_embedder_is_wired_without_loading_model(tmp_path: Path) -> None:
    container = Container(RuntimeSettings(data_dir=tmp_path), ensure_layout(tmp_path))

    embedder = container.embedder

    assert isinstance(embedder, FastEmbedAdapter)
    assert embedder.dimension == 1024


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
