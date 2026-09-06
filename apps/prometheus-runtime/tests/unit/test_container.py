"""Tests for lazy composition-root providers."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from adapters.inbound.http.app import create_app
from adapters.outbound.filesystem.data_dir import ensure_layout
from application.ports.embedder import Embedder
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from domain.errors import AdapterNotConfiguredError


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
