"""SQLite persistence for per-Vault settings."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from adapters.outbound.sqlite.errors import wrap_driver_errors
from application.ports.vault_settings_store import VaultSettingsStore
from domain.value_objects.ignored_folders import IgnoredFolders


class SqliteVaultSettingsStore(VaultSettingsStore):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @wrap_driver_errors
    def load_ignored_folders(self) -> IgnoredFolders:
        rows = self._connection.execute(
            "SELECT folder FROM vault_ignored_folders ORDER BY folder",
        ).fetchall()
        return IgnoredFolders.from_strings(row["folder"] for row in rows)

    @wrap_driver_errors
    def save_ignored_folders(self, folders: Sequence[str]) -> IgnoredFolders:
        ignored = IgnoredFolders.from_strings(folders)
        self._connection.execute("DELETE FROM vault_ignored_folders")
        self._connection.executemany(
            "INSERT INTO vault_ignored_folders (folder) VALUES (?)",
            [(folder.value,) for folder in ignored.folders if folder.value != ".obsidian"],
        )
        return ignored
