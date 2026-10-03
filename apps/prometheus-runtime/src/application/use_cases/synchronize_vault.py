"""Reconcile a plugin-provided Vault snapshot with the manifest."""

from application.dto.vault_sync import VaultSnapshot, VaultSyncSummary
from application.ports.document_repository import DocumentRepository
from application.ports.vault_settings_store import VaultSettingsStore
from application.use_cases.remove_document import RemoveDocument
from application.use_cases.rename_document import RenameDocument
from domain.value_objects.ignored_folders import IgnoredFolders


class SynchronizeVault:
    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        remove_document: RemoveDocument,
        rename_document: RenameDocument,
        vault_settings_store: VaultSettingsStore | None = None,
    ) -> None:
        self._documents = document_repository
        self._remove = remove_document
        self._rename = rename_document
        self._vault_settings = vault_settings_store

    async def execute(self, snapshot: VaultSnapshot) -> VaultSyncSummary:
        ignored = (
            self._vault_settings.load_ignored_folders()
            if self._vault_settings is not None
            else IgnoredFolders.empty()
        )
        manifest = {state.document_id: state for state in self._documents.list_states()}
        incoming = {
            entry.document_id: entry
            for entry in snapshot.entries
            if not ignored.covers(entry.relative_path)
        }

        deleted = tuple(document_id for document_id in manifest if document_id not in incoming)
        for document_id in deleted:
            await self._remove.execute(document_id)

        added = []
        changed = []
        renamed = []
        unchanged = []
        for entry in incoming.values():
            state = manifest.get(entry.document_id)
            if state is None:
                added.append(entry)
            elif state.content_hash != entry.content_hash:
                changed.append(entry)
            elif state.relative_path != entry.relative_path:
                await self._rename.execute(entry.document_id, entry.relative_path)
                renamed.append(entry)
            else:
                unchanged.append(entry)

        return VaultSyncSummary(
            added=tuple(added),
            changed=tuple(changed),
            renamed=tuple(renamed),
            unchanged=tuple(unchanged),
            deleted=deleted,
        )
