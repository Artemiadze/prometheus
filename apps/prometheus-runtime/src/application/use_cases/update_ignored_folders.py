"""Persist ignored folders and drop indexed documents they cover."""

from __future__ import annotations

from collections.abc import Sequence

from application.dto.ignored_folders import IgnoredFoldersUpdateResult
from application.ports.document_repository import DocumentRepository
from application.ports.vault_settings_store import VaultSettingsStore
from application.use_cases.remove_document import RemoveDocument


class UpdateIgnoredFolders:
    def __init__(
        self,
        *,
        vault_settings_store: VaultSettingsStore,
        document_repository: DocumentRepository,
        remove_document: RemoveDocument,
    ) -> None:
        self._settings = vault_settings_store
        self._documents = document_repository
        self._remove = remove_document

    async def execute(self, folders: Sequence[str]) -> IgnoredFoldersUpdateResult:
        ignored = self._settings.save_ignored_folders(folders)
        removed = 0
        for state in self._documents.list_states():
            if ignored.covers(state.relative_path):
                await self._remove.execute(state.document_id)
                removed += 1
        return IgnoredFoldersUpdateResult(folders=ignored, removed_documents=removed)
