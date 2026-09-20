"""Tests for vault-scoped dependency containers."""

from __future__ import annotations

from pathlib import Path

from adapters.outbound.filesystem.data_dir import ensure_layout
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from bootstrap.container_registry import VaultContainerRegistry
from domain.value_objects.vault_id import VaultId
from fakes.fake_embedder import FakeEmbedder


def test_registry_reuses_each_vault_container_and_isolates_storage(tmp_path: Path) -> None:
    layout = ensure_layout(tmp_path)
    base = Container(RuntimeSettings(data_dir=tmp_path), layout, embedder_factory=FakeEmbedder)
    registry = VaultContainerRegistry(base)

    vault_a = registry.get(VaultId("vault-a"))
    vault_b = registry.get(VaultId("vault-b"))

    assert registry.get(VaultId("vault-a")) is vault_a
    assert vault_a is not vault_b
    _ = vault_a.document_repository
    _ = vault_b.document_repository
    index_a = vault_a.vector_index
    index_b = vault_b.vector_index
    metadata_a = layout.vaults / "vault-a" / "metadata.sqlite"
    metadata_b = layout.vaults / "vault-b" / "metadata.sqlite"
    assert metadata_a != metadata_b
    assert (layout.vaults / "vault-a" / "metadata.sqlite").exists()
    assert (layout.vaults / "vault-b" / "metadata.sqlite").exists()
    assert index_a is not index_b
    assert (layout.vaults / "vault-a" / "qdrant").is_dir()
    assert (layout.vaults / "vault-b" / "qdrant").is_dir()

    registry.close_all()
