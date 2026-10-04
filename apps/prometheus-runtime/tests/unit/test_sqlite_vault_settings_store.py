"""Tests for SQLite vault settings store."""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.outbound.sqlite.database import MetadataDatabase
from adapters.outbound.sqlite.migrations import LATEST_VERSION
from domain.value_objects.relative_path import RelativePath

pytestmark = pytest.mark.unit


def test_migration_includes_vault_ignored_folders(tmp_path: Path) -> None:
    db = MetadataDatabase(tmp_path)
    try:
        version = db._connection.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0]
        assert version == LATEST_VERSION
        db._connection.execute("SELECT 1 FROM vault_ignored_folders LIMIT 1")
    finally:
        db.close()


def test_save_and_load_ignored_folders(tmp_path: Path) -> None:
    db = MetadataDatabase(tmp_path)
    try:
        saved = db.vault_settings.save_ignored_folders(["Templates/", "Archive"])
        loaded = db.vault_settings.load_ignored_folders()
        user_saved = {f.value for f in saved.folders if f.value != ".obsidian"}
        user_loaded = {f.value for f in loaded.folders if f.value != ".obsidian"}
        assert user_saved == user_loaded == {"Templates", "Archive"}
        assert loaded.covers(RelativePath("Templates/note.md"))
    finally:
        db.close()
