"""Single-connection owner for one Vault's SQLite metadata + vector database."""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path

from adapters.outbound.sqlite.connection import open_connection
from adapters.outbound.sqlite.document_repository import SqliteDocumentRepository
from adapters.outbound.sqlite.index_metadata_store import SqliteIndexMetadataStore
from adapters.outbound.sqlite.lexical_index import SqliteLexicalIndex
from adapters.outbound.sqlite.migrations import apply_migrations
from adapters.outbound.sqlite.statistics import SqliteIndexStatisticsReader
from adapters.outbound.sqlite.unit_of_work import SqliteUnitOfWork
from adapters.outbound.sqlite.vault_settings_store import SqliteVaultSettingsStore
from adapters.outbound.sqlite.vector_index import SqliteVecVectorIndex
from application.dto.embedding import EmbeddingFingerprint
from domain.value_objects.vault_id import VaultId

DATABASE_FILENAME = "metadata.sqlite"


class MetadataDatabase:
    """Open one Vault's ``metadata.sqlite``, migrate it, and hand out its adapters."""

    def __init__(self, vault_dir: Path) -> None:
        self._vault_dir = vault_dir.expanduser().resolve()
        self.path = self._vault_dir / DATABASE_FILENAME
        self._connection = open_connection(self.path)
        apply_migrations(self._connection)
        self.documents = SqliteDocumentRepository(self._connection)
        self.index_metadata = SqliteIndexMetadataStore(self._connection)
        self.statistics = SqliteIndexStatisticsReader(self._connection, self._vault_dir)
        self.lexical = SqliteLexicalIndex(self._connection)
        self.vault_settings = SqliteVaultSettingsStore(self._connection)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def vector_index(
        self,
        *,
        vault_id: VaultId,
        embedding_fingerprint: EmbeddingFingerprint,
    ) -> SqliteVecVectorIndex:
        """Build a dense index adapter bound to this database connection."""

        return SqliteVecVectorIndex(
            self._connection,
            vault_id=vault_id,
            embedding_fingerprint=embedding_fingerprint,
        )

    def unit_of_work(self) -> SqliteUnitOfWork:
        """Return a fresh transaction boundary bound to the shared connection."""

        return SqliteUnitOfWork(self._connection)

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._connection.close()
