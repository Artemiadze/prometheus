"""Contract-oriented tests for application-port fakes."""

import asyncio
from datetime import UTC, datetime

from application.dto.embedding import EmbeddingFingerprint
from application.dto.index_fingerprint import IndexFingerprint
from application.dto.indexing import IndexingProgress
from application.dto.job import Job, JobStatus
from application.dto.llm import LocalLlmModel
from application.dto.statistics import IndexStatistics
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
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document, compute_content_hash
from domain.entities.search_hit import SearchHit
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId
from fakes import (
    FakeChunker,
    FakeDocumentRepository,
    FakeEmbedder,
    FakeIndexMetadataStore,
    FakeIndexStatisticsReader,
    FakeJobStore,
    FakeLanguageModel,
    FakeMarkdownParser,
    FakeProgressReporter,
    FakeReranker,
    FakeTokenCounter,
    FakeUnitOfWork,
    FakeVectorIndex,
)


def _document() -> Document:
    return Document.create(
        id=DocumentId("document-01"),
        vault_id=VaultId("vault-01"),
        relative_path="Notes/Testing.md",
        content="Deterministic fake content",
        revision=1,
        modified_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _chunk(index: int, text: str) -> Chunk:
    document_id = DocumentId("document-01")
    return Chunk(
        id=ChunkId.from_parts(document_id, ("Testing",), index),
        document_id=document_id,
        text=text,
        heading_path=("Testing",),
        chunk_index=index,
        char_range=CharRange(index * 100, index * 100 + len(text)),
        token_count=max(1, len(text.split())),
        content_hash=compute_content_hash(text),
    )


def test_fakes_structurally_satisfy_all_ports() -> None:
    parser: MarkdownParser = FakeMarkdownParser()
    chunker: Chunker = FakeChunker()
    counter: TokenCounter = FakeTokenCounter()
    embedder: Embedder = FakeEmbedder()
    index: VectorIndex = FakeVectorIndex()
    reranker: Reranker = FakeReranker()
    repository: DocumentRepository = FakeDocumentRepository()
    unit_of_work: UnitOfWork = FakeUnitOfWork()
    jobs: JobStore = FakeJobStore()
    progress: ProgressReporter = FakeProgressReporter()
    language_model: LanguageModel = FakeLanguageModel()
    metadata_store: IndexMetadataStore = FakeIndexMetadataStore()
    statistics_reader: IndexStatisticsReader = FakeIndexStatisticsReader()

    assert all(
        dependency is not None
        for dependency in (
            parser,
            chunker,
            counter,
            embedder,
            index,
            reranker,
            repository,
            unit_of_work,
            jobs,
            progress,
            language_model,
            metadata_store,
            statistics_reader,
        )
    )


def test_fake_parser_chunker_and_counter_form_a_small_pipeline() -> None:
    parsed = FakeMarkdownParser().parse(_document())
    chunks = FakeChunker().chunk(parsed)

    assert len(chunks) == 1
    assert chunks[0].text == "Deterministic fake content"
    assert FakeTokenCounter().count(chunks[0].text) == 3


def test_fake_embedder_is_deterministic() -> None:
    chunk = _chunk(0, "same text")
    embedder = FakeEmbedder(dimension=8)

    first = embedder.embed_documents((chunk,))[0]
    second = embedder.embed_documents((chunk,))[0]

    assert first == second
    assert len(first) == embedder.dimension
    assert embedder.embed_query("same text") == first


def test_fake_vector_index_searches_and_replaces_documents() -> None:
    first = _chunk(0, "first")
    second = _chunk(1, "second")
    index = FakeVectorIndex()
    index.upsert(_document(), (first, second), ((1.0, 0.0), (0.0, 1.0)))

    hits = index.search((1.0, 0.0), limit=2)

    assert [hit.chunk for hit in hits] == [first, second]
    assert [hit.score for hit in hits] == [1.0, 0.0]

    index.upsert(_document(), (second,), ((0.0, 1.0),))
    assert [hit.chunk for hit in index.search((1.0, 0.0), 10)] == [second]


def test_fake_repository_reads_state_and_paths() -> None:
    document = _document()
    chunk = _chunk(0, "Deterministic fake content")
    repository = FakeDocumentRepository()
    indexed_at = datetime(2026, 1, 2, tzinfo=UTC)

    repository.save_indexed(document, (chunk,), indexed_at)

    state = repository.get_state(document.id)
    assert state is not None
    assert state.relative_path == document.relative_path
    assert state.content_hash == document.content_hash
    assert state.indexed_at == indexed_at
    assert state.chunk_count == 1
    assert repository.list_relative_paths() == (document.relative_path,)
    assert repository.list_states() == (state,)

    repository.delete(document.id)
    assert repository.get_state(document.id) is None
    repository.delete(document.id)  # idempotent


def test_fake_index_metadata_store_and_statistics_reader_hold_fixed_state() -> None:
    metadata_store = FakeIndexMetadataStore()
    assert metadata_store.load() is None

    fingerprint = IndexFingerprint(
        embedding=EmbeddingFingerprint("fastembed", "test/model", 4),
        parser_version=1,
        chunker_version=1,
        payload_schema_version=1,
        chunk_size=700,
        chunk_overlap=80,
    )
    metadata_store.save(fingerprint)
    assert metadata_store.load() == fingerprint

    statistics_reader = FakeIndexStatisticsReader()
    assert statistics_reader.read() == IndexStatistics(0, 0, None, 0)


def test_fake_language_model_echoes_context_without_network() -> None:
    model = FakeLanguageModel()

    generation = asyncio.run(
        model.generate(
            "Question: What is in the Vault?\nContext: Vault evidence",
            temperature=0.1,
            context_size=2048,
            max_output_tokens=256,
        )
    )

    assert "What is in the Vault?" in generation.text
    assert "Vault evidence" in generation.text
    assert asyncio.run(model.is_available())
    assert asyncio.run(model.list_models()) == (LocalLlmModel("fake-model", 0),)


def test_remaining_stateful_fakes_record_calls() -> None:
    hit = SearchHit(_chunk(0, "evidence"), 0.9)
    reranker = FakeReranker()
    assert reranker.rerank("query", (hit,)) == (hit,)

    unit_of_work = FakeUnitOfWork()
    with unit_of_work:
        unit_of_work.commit()
    assert unit_of_work.committed
    assert not unit_of_work.rolled_back

    jobs = FakeJobStore()
    job = jobs.create()
    updated = Job(job.id, JobStatus.RUNNING, 0.5)
    jobs.update(updated)
    assert jobs.get(job.id) == updated

    reporter = FakeProgressReporter()
    progress = IndexingProgress(1, 2, 3)
    reporter.report(job.id, progress)
    assert reporter.updates == [(job.id, progress)]
