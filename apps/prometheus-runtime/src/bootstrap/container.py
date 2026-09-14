"""Composition root for application ports and concrete adapters."""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property

from adapters.outbound.fastembed.adapter import FastEmbedAdapter
from adapters.outbound.filesystem.data_dir import DataDirLayout, vault_dir
from adapters.outbound.qdrant.adapter import QdrantLocalVectorIndex
from adapters.outbound.sqlite.database import MetadataDatabase
from application.dto.index_fingerprint import (
    CHUNKER_ALGORITHM_VERSION,
    PARSER_SCHEMA_VERSION,
    PAYLOAD_SCHEMA_VERSION,
    IndexFingerprint,
)
from application.ports.document_repository import DocumentRepository
from application.ports.embedder import Embedder
from application.ports.index_metadata_store import IndexMetadataStore
from application.ports.index_statistics_reader import IndexStatisticsReader
from application.ports.language_model import LanguageModel
from application.ports.unit_of_work import UnitOfWork
from application.ports.vector_index import VectorIndex
from bootstrap.config import RuntimeSettings
from domain.errors import AdapterNotConfiguredError
from domain.value_objects.vault_id import VaultId


def _resolve[T](factory: Callable[[], T] | None, port_name: str) -> T:
    if factory is None:
        raise AdapterNotConfiguredError(
            f"{port_name} adapter is not configured; install it in bootstrap.container"
        )
    return factory()


class Container:
    """Lazily construct heavy adapters at their first use."""

    def __init__(
        self,
        settings: RuntimeSettings,
        layout: DataDirLayout,
        *,
        vault_id: VaultId | None = None,
        embedder_factory: Callable[[], Embedder] | None = None,
        vector_index_factory: Callable[[], VectorIndex] | None = None,
        language_model_factory: Callable[[], LanguageModel] | None = None,
        document_repository_factory: Callable[[], DocumentRepository] | None = None,
        unit_of_work_factory: Callable[[], UnitOfWork] | None = None,
        index_metadata_store_factory: Callable[[], IndexMetadataStore] | None = None,
        index_statistics_factory: Callable[[], IndexStatisticsReader] | None = None,
    ) -> None:
        self.settings = settings
        self.layout = layout
        self._vault_id = vault_id
        self._embedder_factory = embedder_factory or self._build_embedder
        self._vector_index_factory = vector_index_factory or self._build_vector_index
        self._language_model_factory = language_model_factory
        self._document_repository_factory = (
            document_repository_factory or self._build_document_repository
        )
        self._unit_of_work_factory = unit_of_work_factory or self._build_unit_of_work
        self._index_metadata_store_factory = (
            index_metadata_store_factory or self._build_index_metadata_store
        )
        self._index_statistics_factory = index_statistics_factory or self._build_index_statistics

    def _build_embedder(self) -> Embedder:
        if self.settings.embedding_provider.casefold() != "fastembed":
            raise AdapterNotConfiguredError(
                f"Embedding provider {self.settings.embedding_provider!r} is not configured"
            )
        return FastEmbedAdapter(
            model_id=self.settings.embedding_model,
            cache_dir=self.layout.embeddings,
            batch_size=self.settings.embedding_batch_size,
            threads=self.settings.embedding_threads,
            allow_download=self.settings.embedding_allow_download,
        )

    def _build_vector_index(self) -> VectorIndex:
        if self._vault_id is None:
            raise AdapterNotConfiguredError(
                "VectorIndex adapter is not configured; provide a vault_id to Container"
            )
        return QdrantLocalVectorIndex(
            vault_dir=vault_dir(self.layout, self._vault_id.value),
            embedding_fingerprint=self.embedder.fingerprint,
        )

    @cached_property
    def _metadata_database(self) -> MetadataDatabase:
        if self._vault_id is None:
            raise AdapterNotConfiguredError(
                "Metadata store adapter is not configured; provide a vault_id to Container"
            )
        return MetadataDatabase(vault_dir(self.layout, self._vault_id.value))

    def _build_document_repository(self) -> DocumentRepository:
        return self._metadata_database.documents

    def _build_unit_of_work(self) -> UnitOfWork:
        return self._metadata_database.unit_of_work()

    def _build_index_metadata_store(self) -> IndexMetadataStore:
        return self._metadata_database.index_metadata

    def _build_index_statistics(self) -> IndexStatisticsReader:
        return self._metadata_database.statistics

    @cached_property
    def embedder(self) -> Embedder:
        return _resolve(self._embedder_factory, "Embedder")

    @cached_property
    def vector_index(self) -> VectorIndex:
        return _resolve(self._vector_index_factory, "VectorIndex")

    @cached_property
    def language_model(self) -> LanguageModel:
        return _resolve(self._language_model_factory, "LanguageModel")

    @cached_property
    def document_repository(self) -> DocumentRepository:
        return _resolve(self._document_repository_factory, "DocumentRepository")

    @cached_property
    def unit_of_work(self) -> UnitOfWork:
        return _resolve(self._unit_of_work_factory, "UnitOfWork")

    @cached_property
    def index_metadata_store(self) -> IndexMetadataStore:
        return _resolve(self._index_metadata_store_factory, "IndexMetadataStore")

    @cached_property
    def index_statistics(self) -> IndexStatisticsReader:
        return _resolve(self._index_statistics_factory, "IndexStatisticsReader")

    @cached_property
    def active_index_fingerprint(self) -> IndexFingerprint:
        """Assemble the fingerprint of the runtime's currently active settings."""

        return IndexFingerprint(
            embedding=self.embedder.fingerprint,
            parser_version=PARSER_SCHEMA_VERSION,
            chunker_version=CHUNKER_ALGORITHM_VERSION,
            payload_schema_version=PAYLOAD_SCHEMA_VERSION,
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
