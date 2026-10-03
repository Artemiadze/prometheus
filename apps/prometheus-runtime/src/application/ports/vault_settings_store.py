"""Per-Vault settings persisted by the runtime."""

from collections.abc import Sequence
from typing import Protocol

from domain.value_objects.ignored_folders import IgnoredFolders


class VaultSettingsStore(Protocol):
    """Load and save Vault-specific configuration such as ignored folders."""

    def load_ignored_folders(self) -> IgnoredFolders: ...

    def save_ignored_folders(self, folders: Sequence[str]) -> IgnoredFolders: ...
