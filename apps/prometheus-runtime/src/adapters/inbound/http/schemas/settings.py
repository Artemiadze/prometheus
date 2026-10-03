"""HTTP schemas for Vault settings."""

from __future__ import annotations

from adapters.inbound.http.schemas.common import ApiSchema
from application.dto.ignored_folders import IgnoredFoldersUpdateResult
from domain.value_objects.ignored_folders import IgnoredFolders


class IgnoredFoldersRequest(ApiSchema):
    folders: tuple[str, ...] = ()


class IgnoredFoldersResponse(ApiSchema):
    folders: tuple[str, ...]
    removed_documents: int | None = None

    @classmethod
    def from_ignored(
        cls, ignored: IgnoredFolders, *, removed_documents: int | None = None
    ) -> IgnoredFoldersResponse:
        user_folders = tuple(
            folder.value for folder in ignored.folders if folder.value != ".obsidian"
        )
        return cls(folders=user_folders, removed_documents=removed_documents)

    @classmethod
    def from_update(cls, result: IgnoredFoldersUpdateResult) -> IgnoredFoldersResponse:
        return cls.from_ignored(result.folders, removed_documents=result.removed_documents)
