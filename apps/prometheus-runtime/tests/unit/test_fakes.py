"""Contract-oriented tests for application-port fakes."""

from datetime import UTC, datetime

from application.dto.job import Job, JobStatus
from application.ports.chunker import Chunker
from application.ports.document_repository import DocumentRepository
from application.ports.embedder import Embedder
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
    index.upsert(first.document_id, (first, second), ((1.0, 0.0), (0.0, 1.0)))

    hits = index.search((1.0, 0.0), limit=2)

    assert [hit.chunk for hit in hits] == [first, second]
    assert [hit.score for hit in hits] == [1.0, 0.0]

    index.upsert(first.document_id, (second,), ((0.0, 1.0),))
    assert [hit.chunk for hit in index.search((1.0, 0.0), 10)] == [second]


def test_fake_repository_reads_documents_and_paths() -> None:
    document = _document()
    repository = FakeDocumentRepository()
    repository.save(document)

    assert repository.get(document.id) == document
    assert repository.list_relative_paths() == (document.relative_path,)


def test_fake_language_model_echoes_context_without_network() -> None:
    chunk = _chunk(0, "Vault evidence")
    model = FakeLanguageModel()

    answer = model.generate(
        "What is in the Vault?",
        (chunk,),
        temperature=0.1,
        context_size=2048,
    )

    assert "What is in the Vault?" in answer
    assert "Vault evidence" in answer
    assert model.is_available()
    assert model.list_models() == ("fake-model",)


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
    reporter.report(job.id, 0.5)
    assert reporter.updates == [(job.id, 0.5)]
