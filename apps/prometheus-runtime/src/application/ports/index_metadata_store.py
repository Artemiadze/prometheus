"""Index fingerprint persistence application port."""

from typing import Protocol

from application.dto.index_fingerprint import IndexFingerprint


class IndexMetadataStore(Protocol):
    """Persist and read the one active index fingerprint for a Vault."""

    def load(self) -> IndexFingerprint | None: ...

    def save(self, fingerprint: IndexFingerprint) -> None: ...
