"""Composition root for application ports and concrete adapters."""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from importlib.metadata import version

from adapters.outbound.fastembed.adapter import FastEmbedAdapter
from adapters.outbound.fastembed.reranker import FastEmbedReranker
from adapters.outbound.filesystem.data_dir import DataDirLayout, vault_dir
from adapters.outbound.filesystem.index_rebuild import (
    FilesystemIndexRebuildWorkspace,
    build_staging_index_document,
    recover_interrupted_promotion,
)
from adapters.outbound.markdown.chunker import HeadingAwareChunker
from adapters.outbound.markdown.parser import ObsidianMarkdownParser
from adapters.outbound.markdown.token_counter import FastEmbedTokenizerCounter
from adapters.outbound.ollama.adapter import OllamaLanguageModel
from adapters.outbound.qdrant.adapter import QdrantLocalVectorIndex
from adapters.outbound.sqlite.database import MetadataDatabase
from adapters.outbound.sqlite.jobs_database import JobsDatabase
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
from application.ports.index_rebuild import IndexRebuildWorkspace
from application.ports.index_statistics_reader import IndexStatisticsReader
from application.ports.job_store import JobStore
from application.ports.language_model import LanguageModel
from application.ports.lexical_index import LexicalIndex
from application.ports.markdown_parser import MarkdownParser
from application.ports.progress_reporter import ProgressReporter
from application.ports.reranker import Reranker
from application.ports.token_counter import TokenCounter
from application.ports.unit_of_work import UnitOfWork
from application.ports.vault_settings_store import VaultSettingsStore
from application.ports.vector_index import VectorIndex
from application.services.document_indexing_queue import SerializedDocumentIndexing
from application.services.retrieval import RetrievalService
from application.use_cases.answer_question import AnswerQuestion
from application.use_cases.get_runtime_status import GetRuntimeStatus
from application.use_cases.index_document import IndexDocument
from application.use_cases.reindex_vault import ReindexVault
from application.use_cases.remove_document import RemoveDocument
from application.use_cases.rename_document import RenameDocument
from application.use_cases.search_notes import SearchNotes
from application.use_cases.synchronize_vault import SynchronizeVault
from application.use_cases.update_ignored_folders import UpdateIgnoredFolders
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
        lexical_index_factory: Callable[[], LexicalIndex] | None = None,
        markdown_parser_factory: Callable[[], MarkdownParser] | None = None,
        chunker_factory: Callable[[], Chunker] | None = None,
        token_counter_factory: Callable[[], TokenCounter] | None = None,
        reranker_factory: Callable[[], Reranker] | None = None,
        job_store_factory: Callable[[], JobStore] | None = None,
        progress_reporter_factory: Callable[[], ProgressReporter] | None = None,
        rebuild_workspace_factory: Callable[[], IndexRebuildWorkspace] | None = None,
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
        self._lexical_index_factory = lexical_index_factory or self._build_lexical_index
        self._markdown_parser_factory = markdown_parser_factory or self._build_markdown_parser
        self._chunker_factory = chunker_factory or self._build_chunker
        self._token_counter_factory = token_counter_factory or self._build_token_counter
        selected_reranker_factory: Callable[[], Reranker] | None
        if reranker_factory is not None:
            selected_reranker_factory = reranker_factory
        elif settings.reranker_enabled:
            selected_reranker_factory = self._build_reranker
        else:
            selected_reranker_factory = None
        self._reranker_factory = selected_reranker_factory
        self._job_store_factory = job_store_factory or self._build_job_store
        self._progress_reporter_factory = progress_reporter_factory or self._build_progress_reporter
        self._rebuild_workspace_factory = rebuild_workspace_factory or self._build_rebuild_workspace

    def _build_reranker(self) -> Reranker:
        return FastEmbedReranker(
            model_id=self.settings.reranker_model,
            cache_dir=self.layout.embeddings,
            batch_size=self.settings.reranker_batch_size,
            threads=self.settings.embedding_threads,
            allow_download=self.settings.reranker_allow_download,
        )

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
            vault_id=self._vault_id,
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
        return self._jobs_database.job_store

    def _build_progress_reporter(self) -> ProgressReporter:
        return self._jobs_database.progress_reporter

    def _build_rebuild_workspace(self) -> IndexRebuildWorkspace:
        if self._vault_id is None:
            raise AdapterNotConfiguredError(
                "Index rebuild workspace requires a vault_id; provide a vault_id to Container"
            )
        vault_id = self._vault_id
        vault_path = vault_dir(self.layout, vault_id.value)

        def build(
            documents: DocumentRepository,
            vectors: VectorIndex,
            metadata: IndexMetadataStore,
            unit_of_work: UnitOfWork,
            lexical_index: LexicalIndex,
        ) -> IndexDocument:
            return build_staging_index_document(
                vault_id=vault_id,
                parser=self.markdown_parser,
                chunker=self.chunker,
                embedder=self.embedder,
                document_repository=documents,
                vector_index=vectors,
                index_metadata_store=metadata,
                unit_of_work=unit_of_work,
                lexical_index=lexical_index,
                active_fingerprint=self.active_index_fingerprint,
                max_document_chars=self.settings.max_document_chars,
                max_chunks_per_document=self.settings.max_chunks_per_document,
            )

        return FilesystemIndexRebuildWorkspace(
            vault_path,
            vault_id=vault_id,
            embedding_fingerprint=self.embedder.fingerprint,
            build_index_document=build,
            release_active_storage=self.release_vault_storage,
        )

    def release_vault_storage(self) -> None:
        """Close and drop cached Vault persistence so a promoted index can be reopened."""

        if "_metadata_database" in self.__dict__:
            self._metadata_database.close()
            del self.__dict__["_metadata_database"]
        if "vector_index" in self.__dict__:
            index = self.__dict__.pop("vector_index")
            close = getattr(index, "close", None)
            if callable(close):
                close()
        for name in (
            "document_repository",
            "unit_of_work",
            "index_metadata_store",
            "index_statistics",
            "lexical_index",
            "vault_settings_store",
            "update_ignored_folders",
            "rename_document",
            "index_document",
            "serialized_index_document",
            "remove_document",
            "synchronize_vault",
            "retrieval",
            "search_notes",
            "answer_question",
            "reindex_vault",
            "runtime_status",
        ):
            self.__dict__.pop(name, None)

    @cached_property
    def _jobs_database(self) -> JobsDatabase:
        return JobsDatabase(self.layout.state)

    @cached_property
    def _metadata_database(self) -> MetadataDatabase:
        if self._vault_id is None:
            raise AdapterNotConfiguredError(
                "Metadata store adapter is not configured; provide a vault_id to Container"
            )
        path = vault_dir(self.layout, self._vault_id.value)
        recover_interrupted_promotion(path)
        return MetadataDatabase(path)

    def _build_document_repository(self) -> DocumentRepository:
        return self._metadata_database.documents

    def _build_unit_of_work(self) -> UnitOfWork:
        return self._metadata_database.unit_of_work()

    def _build_index_metadata_store(self) -> IndexMetadataStore:
        return self._metadata_database.index_metadata

    def _build_index_statistics(self) -> IndexStatisticsReader:
        return self._metadata_database.statistics

    def _build_lexical_index(self) -> LexicalIndex:
        return self._metadata_database.lexical

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
    def lexical_index(self) -> LexicalIndex:
        return _resolve(self._lexical_index_factory, "LexicalIndex")

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
    def vault_settings_store(self) -> VaultSettingsStore:
        return self._metadata_database.vault_settings

    @cached_property
    def remove_document(self) -> RemoveDocument:
        return RemoveDocument(
            document_repository=self.document_repository,
            vector_index=self.vector_index,
            lexical_index=self.lexical_index,
            unit_of_work=self.unit_of_work,
        )

    @cached_property
    def rename_document(self) -> RenameDocument:
        return RenameDocument(
            document_repository=self.document_repository,
            vector_index=self.vector_index,
            lexical_index=self.lexical_index,
            unit_of_work=self.unit_of_work,
            vault_settings_store=self.vault_settings_store,
            remove_document=self.remove_document,
        )

    def close(self) -> None:
        """Release SQLite and Qdrant resources owned by this container."""

        if "_metadata_database" in self.__dict__:
            self._metadata_database.close()
        if "vector_index" in self.__dict__:
            index = self.vector_index
            close = getattr(index, "close", None)
            if callable(close):
                close()
        if "_jobs_database" in self.__dict__ and self._vault_id is None:
            self._jobs_database.close()

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
            lexical_index=self.lexical_index,
            document_repository=self.document_repository,
            unit_of_work=self.unit_of_work,
            index_metadata_store=self.index_metadata_store,
            active_fingerprint=self.active_index_fingerprint,
            rename_document=self.rename_document,
            max_document_chars=self.settings.max_document_chars,
            max_chunks_per_document=self.settings.max_chunks_per_document,
            vault_settings_store=self.vault_settings_store,
        )

    @cached_property
    def serialized_index_document(self) -> SerializedDocumentIndexing:
        return SerializedDocumentIndexing(self.index_document)

    @cached_property
    def synchronize_vault(self) -> SynchronizeVault:
        return SynchronizeVault(
            document_repository=self.document_repository,
            remove_document=self.remove_document,
            rename_document=self.rename_document,
            vault_settings_store=self.vault_settings_store,
        )

    @cached_property
    def update_ignored_folders(self) -> UpdateIgnoredFolders:
        return UpdateIgnoredFolders(
            vault_settings_store=self.vault_settings_store,
            document_repository=self.document_repository,
            remove_document=self.remove_document,
        )

    @cached_property
    def retrieval(self) -> RetrievalService:
        return RetrievalService(
            embedder=self.embedder,
            vector_index=self.vector_index,
            document_repository=self.document_repository,
            index_metadata_store=self.index_metadata_store,
            active_fingerprint=self.active_index_fingerprint,
            reranker=self.reranker,
            lexical_index=self.lexical_index,
            retrieval_mode=self.settings.retrieval_mode,
            hybrid_rrf_k=self.settings.hybrid_rrf_k,
            hybrid_dense_weight=self.settings.hybrid_dense_weight,
            hybrid_lexical_weight=self.settings.hybrid_lexical_weight,
            hybrid_candidate_multiplier=self.settings.hybrid_candidate_multiplier,
            top_k=self.settings.top_k,
            rerank_candidate_limit=self.settings.reranker_candidate_limit,
            vault_settings_store=self.vault_settings_store,
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
    def rebuild_workspace(self) -> IndexRebuildWorkspace:
        return _resolve(self._rebuild_workspace_factory, "IndexRebuildWorkspace")

    @cached_property
    def reindex_vault(self) -> ReindexVault:
        if self._vault_id is None:
            raise AdapterNotConfiguredError("ReindexVault requires a vault_id")
        return ReindexVault(
            vault_id=self._vault_id,
            rebuild_workspace=self.rebuild_workspace,
            active_fingerprint=self.active_index_fingerprint,
            job_store=self.job_store,
            progress_reporter=self.progress_reporter,
            progress_interval=self.settings.job_progress_interval,
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
