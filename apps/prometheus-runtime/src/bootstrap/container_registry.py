"""Lazily create isolated Vault-scoped containers for HTTP requests."""

from __future__ import annotations

from bootstrap.container import Container
from domain.value_objects.vault_id import VaultId


class VaultContainerRegistry:
    """Reuse process-wide services while isolating each Vault's persistence."""

    def __init__(self, base: Container) -> None:
        self._base = base
        self._by_vault: dict[VaultId, Container] = {}

    def get(self, vault_id: VaultId) -> Container:
        container = self._by_vault.get(vault_id)
        if container is None:
            container = Container(
                self._base.settings,
                self._base.layout,
                vault_id=vault_id,
                embedder_factory=lambda: self._base.embedder,
                language_model_factory=lambda: self._base.language_model,
                markdown_parser_factory=lambda: self._base.markdown_parser,
                chunker_factory=lambda: self._base.chunker,
                token_counter_factory=lambda: self._base.token_counter,
                job_store_factory=lambda: self._base.job_store,
                progress_reporter_factory=lambda: self._base.progress_reporter,
            )
            self._by_vault[vault_id] = container
        return container

    def close_all(self) -> None:
        """Close every vault-scoped container opened during this process."""

        for container in self._by_vault.values():
            container.close()
        self._by_vault.clear()
