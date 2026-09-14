"""SQLite Local outbound adapter (Vault-scoped metadata manifest)."""

from adapters.outbound.sqlite.database import DATABASE_FILENAME, MetadataDatabase
from adapters.outbound.sqlite.document_repository import SqliteDocumentRepository
from adapters.outbound.sqlite.errors import MetadataStoreError, SchemaDowngradeError
from adapters.outbound.sqlite.index_metadata_store import SqliteIndexMetadataStore
from adapters.outbound.sqlite.statistics import SqliteIndexStatisticsReader
from adapters.outbound.sqlite.unit_of_work import SqliteUnitOfWork

__all__ = [
    "DATABASE_FILENAME",
    "MetadataDatabase",
    "MetadataStoreError",
    "SchemaDowngradeError",
    "SqliteDocumentRepository",
    "SqliteIndexMetadataStore",
    "SqliteIndexStatisticsReader",
    "SqliteUnitOfWork",
]
