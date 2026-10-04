"""Tests for local FastEmbed adapter behavior without loading an ONNX model."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from adapters.outbound.fastembed.adapter import EmbeddingBackend, FastEmbedAdapter
from adapters.outbound.fastembed.errors import (
    EmbeddingBatchError,
    EmbeddingDimensionMismatchError,
    EmbeddingModelUnavailableError,
)
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import compute_content_hash
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId


class RecordingBackend:
    def __init__(self, dimension: int = 4, fail_on_call: int | None = None) -> None:
        self.dimension = dimension
        self.fail_on_call = fail_on_call
        self.calls: list[tuple[str, ...]] = []
        self.batch_sizes: list[int] = []

    def embed(
        self,
        texts: Sequence[str],
        *,
        batch_size: int,
    ) -> Sequence[Sequence[float]]:
        self.calls.append(tuple(texts))
        self.batch_sizes.append(batch_size)
        if self.fail_on_call == len(self.calls):
            raise RuntimeError("backend failed")
        return tuple(
            tuple(float(index) for index in range(self.dimension)) for _ in texts
        )


class RecordingFactory:
    def __init__(
        self,
        backend: EmbeddingBackend,
        *,
        fail_local: bool = False,
        fail_online: bool = False,
    ) -> None:
        self.backend = backend
        self.fail_local = fail_local
        self.fail_online = fail_online
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        *,
        model_name: str,
        cache_dir: str,
        threads: int | None,
        local_files_only: bool,
    ) -> EmbeddingBackend:
        self.calls.append(
            {
                "model_name": model_name,
                "cache_dir": cache_dir,
                "threads": threads,
                "local_files_only": local_files_only,
            }
        )
        if (local_files_only and self.fail_local) or (
            not local_files_only and self.fail_online
        ):
            raise RuntimeError("model unavailable")
        return self.backend


def _chunk(index: int, text: str | None = None) -> Chunk:
    document_id = DocumentId("document-01")
    content = text or f"private chunk {index}"
    return Chunk(
        id=ChunkId.from_parts(document_id, ("Testing",), 1, index),
        document_id=document_id,
        text=content,
        heading_path=("Testing",),
        chunk_index=index,
        char_range=CharRange(index * 100, index * 100 + len(content)),
        token_count=max(1, len(content.split())),
        content_hash=compute_content_hash(content),
        heading_line=0,
        heading_occurrence=1,
    )


def _adapter(
    tmp_path: Path,
    factory: RecordingFactory,
    *,
    batch_size: int = 64,
    threads: int | None = 2,
    allow_download: bool = False,
) -> FastEmbedAdapter:
    return FastEmbedAdapter(
        model_id="intfloat/multilingual-e5-large",
        cache_dir=tmp_path / "models" / "embeddings",
        batch_size=batch_size,
        threads=threads,
        allow_download=allow_download,
        backend_factory=factory,
        dimension_resolver=lambda _: 4,
    )


def test_e5_uses_distinct_passage_and_query_prefixes(tmp_path: Path) -> None:
    backend = RecordingBackend()
    adapter = _adapter(tmp_path, RecordingFactory(backend))

    adapter.embed_documents((_chunk(0, "document text"),))
    adapter.embed_query("search text")

    assert backend.calls == [("passage: document text",), ("query: search text",)]


def test_metadata_matches_declared_model(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path, RecordingFactory(RecordingBackend()))

    assert adapter.provider == "fastembed"
    assert adapter.model_id == "intfloat/multilingual-e5-large"
    assert adapter.dimension == 4
    assert adapter.fingerprint.dimension == 4


def test_one_thousand_chunks_are_processed_in_bounded_batches(tmp_path: Path) -> None:
    backend = RecordingBackend()
    adapter = _adapter(tmp_path, RecordingFactory(backend), batch_size=64)

    vectors = adapter.embed_documents(tuple(_chunk(index) for index in range(1000)))

    assert len(vectors) == 1000
    assert len(backend.calls) == 16
    assert max(len(batch) for batch in backend.calls) == 64
    assert backend.batch_sizes == [len(batch) for batch in backend.calls]


def test_factory_receives_private_cache_threads_and_local_only_first(
    tmp_path: Path,
) -> None:
    factory = RecordingFactory(RecordingBackend())
    adapter = _adapter(tmp_path, factory, threads=3)

    adapter.embed_query("query")

    assert factory.calls == [
        {
            "model_name": "intfloat/multilingual-e5-large",
            "cache_dir": str((tmp_path / "models" / "embeddings").resolve()),
            "threads": 3,
            "local_files_only": True,
        }
    ]
    assert (tmp_path / "models" / "embeddings").is_dir()


def test_batch_failure_has_diagnostics_without_chunk_text(tmp_path: Path) -> None:
    private_text = "private note body must not leak"
    backend = RecordingBackend(fail_on_call=2)
    adapter = _adapter(tmp_path, RecordingFactory(backend), batch_size=1)

    with pytest.raises(EmbeddingBatchError) as caught:
        adapter.embed_documents((_chunk(0), _chunk(1, private_text)))

    assert caught.value.batch_index == 1
    assert caught.value.processed_count == 1
    assert private_text not in str(caught.value)


def test_strict_offline_does_not_fall_back_to_network(tmp_path: Path) -> None:
    factory = RecordingFactory(RecordingBackend(), fail_local=True)
    adapter = _adapter(tmp_path, factory, allow_download=False)

    with pytest.raises(EmbeddingModelUnavailableError):
        adapter.embed_query("query")

    assert [call["local_files_only"] for call in factory.calls] == [True]


def test_explicit_download_allows_one_online_fallback(tmp_path: Path) -> None:
    factory = RecordingFactory(RecordingBackend(), fail_local=True)
    adapter = _adapter(tmp_path, factory, allow_download=True)

    adapter.embed_query("query")

    assert [call["local_files_only"] for call in factory.calls] == [True, False]


def test_failed_online_fallback_has_stable_error(tmp_path: Path) -> None:
    factory = RecordingFactory(
        RecordingBackend(),
        fail_local=True,
        fail_online=True,
    )
    adapter = _adapter(tmp_path, factory, allow_download=True)

    with pytest.raises(EmbeddingModelUnavailableError) as caught:
        adapter.embed_query("private query")

    assert caught.value.code == "EMBEDDING_MODEL_UNAVAILABLE"
    assert "private query" not in str(caught.value)


def test_vector_dimension_mismatch_is_rejected(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path, RecordingFactory(RecordingBackend(dimension=3)))

    with pytest.raises(EmbeddingDimensionMismatchError) as caught:
        adapter.embed_query("query")

    assert caught.value.expected == 4
    assert caught.value.actual == 3


def test_empty_document_batch_does_not_initialize_model(tmp_path: Path) -> None:
    factory = RecordingFactory(RecordingBackend())
    adapter = _adapter(tmp_path, factory)

    assert adapter.embed_documents(()) == ()
    assert factory.calls == []


def test_unknown_model_has_stable_unavailable_error(tmp_path: Path) -> None:
    def unknown_model(_: str) -> int:
        raise ValueError("unsupported model")

    with pytest.raises(EmbeddingModelUnavailableError):
        FastEmbedAdapter(
            model_id="unknown/model",
            cache_dir=tmp_path,
            backend_factory=RecordingFactory(RecordingBackend()),
            dimension_resolver=unknown_model,
        )
