"""Composition root for application ports and concrete adapters."""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from importlib.metadata import version

from adapters.outbound.fastembed.adapter import FastEmbedAdapter
from adapters.outbound.filesystem.data_dir import DataDirLayout, vault_dir
from adapters.outbound.markdown.chunker import HeadingAwareChunker
from adapters.outbound.markdown.parser import ObsidianMarkdownParser
from adapters.outbound.markdown.token_counter import FastEmbedTokenizerCounter
from adapters.outbound.memory.job_store import InMemoryJobStore
from adapters.outbound.memory.progress_reporter import InMemoryProgressReporter
from adapters.outbound.ollama.adapter import OllamaLanguageModel
from adapters.outbound.qdrant.adapter import QdrantLocalVectorIndex
from adapters.outbound.sqlite.database import MetadataDatabase
from application.dto.index_fingerprint import (
    CHUNKER_ALGORITHM_VERSION,
    PARSER_SCHEMA_VERSION,
    PAYLOAD_SCHEMA_VERSION,
    IndexFingerprint,
)
from application.ports.chunker import Chunker
from application.ports.document_repository import DocumentRepository
from application.ports.embedder import Embedder
from application.ports.index_metadata_store import IndexMetadataStore
from application.ports.index_statistics_reader import IndexStatisticsReader
from application.ports.job_store import JobStore
from application.ports.language_model import LanguageModel
from application.ports.markdown_parser import MarkdownParser
from application.ports.progress_reporter import ProgressReporter
from application.ports.reranker import Reranker
from application.ports.token_counter import TokenCounter
from application.ports.unit_of_work import UnitOfWork
from application.ports.vector_index import VectorIndex
from application.services.retrieval import RetrievalService
from application.use_cases.answer_question import AnswerQuestion
from application.use_cases.get_runtime_status import GetRuntimeStatus
from application.use_cases.index_document import IndexDocument
from application.use_cases.reindex_vault import ReindexVault
from application.use_cases.remove_document import RemoveDocument
from application.use_cases.rename_document import RenameDocument
from application.use_cases.search_notes import SearchNotes
from application.use_cases.synchronize_vault import SynchronizeVault
from bootstrap.config import RuntimeSettings
from domain.errors import AdapterNotConfiguredError
from domain.services.grounding_policy import GroundingPolicy
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
        markdown_parser_factory: Callable[[], MarkdownParser] | None = None,
        chunker_factory: Callable[[], Chunker] | None = None,
        token_counter_factory: Callable[[], TokenCounter] | None = None,
        reranker_factory: Callable[[], Reranker] | None = None,
        job_store_factory: Callable[[], JobStore] | None = None,
        progress_reporter_factory: Callable[[], ProgressReporter] | None = None,
    ) -> None:
        self.settings = settings
        self.layout = layout
        self._vault_id = vault_id
        self._embedder_factory = embedder_factory or self._build_embedder
        self._vector_index_factory = vector_index_factory or self._build_vector_index
        self._language_model_factory = language_model_factory or self._build_language_model
        self._document_repository_factory = (
            document_repository_factory or self._build_document_repository
        )
        self._unit_of_work_factory = unit_of_work_factory or self._build_unit_of_work
        self._index_metadata_store_factory = (
            index_metadata_store_factory or self._build_index_metadata_store
        )
        self._index_statistics_factory = index_statistics_factory or self._build_index_statistics
        self._markdown_parser_factory = markdown_parser_factory or self._build_markdown_parser
        self._chunker_factory = chunker_factory or self._build_chunker
        self._token_counter_factory = token_counter_factory or self._build_token_counter
        self._reranker_factory = reranker_factory
        self._job_store_factory = job_store_factory or self._build_job_store
        self._progress_reporter_factory = progress_reporter_factory or self._build_progress_reporter

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

    def _build_language_model(self) -> LanguageModel:
        return OllamaLanguageModel(
            base_url=self.settings.llm_host,
            model=self.settings.llm_model,
            timeout_seconds=self.settings.llm_timeout_seconds,
        )

    def _build_markdown_parser(self) -> MarkdownParser:
        return ObsidianMarkdownParser()

    def _build_chunker(self) -> Chunker:
        return HeadingAwareChunker(
            max_tokens=self.settings.chunk_size,
            overlap_tokens=self.settings.chunk_overlap,
            token_counter=self.token_counter,
        )

    def _build_token_counter(self) -> TokenCounter:
        return FastEmbedTokenizerCounter(
            model_id=self.settings.embedding_model,
            cache_dir=self.layout.embeddings,
        )

    def _build_job_store(self) -> JobStore:
        return InMemoryJobStore()

    def _build_progress_reporter(self) -> ProgressReporter:
        return InMemoryProgressReporter()

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
    def markdown_parser(self) -> MarkdownParser:
        return _resolve(self._markdown_parser_factory, "MarkdownParser")

    @cached_property
    def chunker(self) -> Chunker:
        return _resolve(self._chunker_factory, "Chunker")

    @cached_property
    def token_counter(self) -> TokenCounter:
        return _resolve(self._token_counter_factory, "TokenCounter")

    @cached_property
    def reranker(self) -> Reranker | None:
        return None if self._reranker_factory is None else self._reranker_factory()

    @cached_property
    def job_store(self) -> JobStore:
        return _resolve(self._job_store_factory, "JobStore")

    @cached_property
    def progress_reporter(self) -> ProgressReporter:
        return _resolve(self._progress_reporter_factory, "ProgressReporter")

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

    @cached_property
    def rename_document(self) -> RenameDocument:
        return RenameDocument(
            document_repository=self.document_repository,
            vector_index=self.vector_index,
            unit_of_work=self.unit_of_work,
        )

    @cached_property
    def index_document(self) -> IndexDocument:
        if self._vault_id is None:
            raise AdapterNotConfiguredError("IndexDocument requires a vault_id")
        return IndexDocument(
            vault_id=self._vault_id,
            parser=self.markdown_parser,
            chunker=self.chunker,
            embedder=self.embedder,
            vector_index=self.vector_index,
            document_repository=self.document_repository,
            unit_of_work=self.unit_of_work,
            index_metadata_store=self.index_metadata_store,
            active_fingerprint=self.active_index_fingerprint,
            rename_document=self.rename_document,
            max_document_chars=self.settings.max_document_chars,
            max_chunks_per_document=self.settings.max_chunks_per_document,
        )

    @cached_property
    def remove_document(self) -> RemoveDocument:
        return RemoveDocument(
            document_repository=self.document_repository,
            vector_index=self.vector_index,
            unit_of_work=self.unit_of_work,
        )

    @cached_property
    def synchronize_vault(self) -> SynchronizeVault:
        return SynchronizeVault(
            document_repository=self.document_repository,
            remove_document=self.remove_document,
            rename_document=self.rename_document,
        )

    @cached_property
    def retrieval(self) -> RetrievalService:
        return RetrievalService(
            embedder=self.embedder,
            vector_index=self.vector_index,
            document_repository=self.document_repository,
            index_metadata_store=self.index_metadata_store,
            reranker=self.reranker,
        )

    @cached_property
    def search_notes(self) -> SearchNotes:
        return SearchNotes(self.retrieval)

    @cached_property
    def answer_question(self) -> AnswerQuestion:
        return AnswerQuestion(
            retrieval=self.retrieval,
            grounding_policy=GroundingPolicy(),
            token_counter=self.token_counter,
            language_model=self.language_model,
            context_size=self.settings.llm_context_size,
            response_token_reserve=self.settings.llm_output_reserve,
            temperature=self.settings.llm_temperature,
        )

    @cached_property
    def reindex_vault(self) -> ReindexVault:
        return ReindexVault(
            index_document=self.index_document,
            remove_document=self.remove_document,
            document_repository=self.document_repository,
            index_metadata_store=self.index_metadata_store,
            active_fingerprint=self.active_index_fingerprint,
            job_store=self.job_store,
            progress_reporter=self.progress_reporter,
        )

    @cached_property
    def runtime_status(self) -> GetRuntimeStatus:
        return GetRuntimeStatus(
            runtime_version=version("prometheus-runtime"),
            llm_model=self.settings.llm_model,
            language_model=self.language_model,
            vector_index=self.vector_index,
            index_metadata_store=self.index_metadata_store,
            index_statistics=self.index_statistics,
            active_fingerprint=self.active_index_fingerprint,
        )
