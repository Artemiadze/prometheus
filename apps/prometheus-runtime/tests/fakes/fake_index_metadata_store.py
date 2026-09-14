"""In-memory IndexMetadataStore for unit tests."""

from __future__ import annotations

from application.dto.index_fingerprint import IndexFingerprint


class FakeIndexMetadataStore:
    """Hold at most one fingerprint in memory, scoped to one test Vault."""

    def __init__(self, fingerprint: IndexFingerprint | None = None) -> None:
        self._fingerprint = fingerprint

    def load(self) -> IndexFingerprint | None:
        return self._fingerprint

    def save(self, fingerprint: IndexFingerprint) -> None:
        self._fingerprint = fingerprint
