"""DTOs for ignored-folder settings."""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.ignored_folders import IgnoredFolders


@dataclass(frozen=True, slots=True)
class IgnoredFoldersUpdateResult:
    folders: IgnoredFolders
    removed_documents: int
