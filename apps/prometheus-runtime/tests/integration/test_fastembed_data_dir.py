"""Integration: FastEmbedAdapter cache_dir under temporary data_dir (PRM-81)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from adapters.outbound.fastembed.adapter import EmbeddingBackend, FastEmbedAdapter
from adapters.outbound.fastembed.errors import EmbeddingModelUnavailableError
from adapters.outbound.filesystem.data_dir import ensure_layout
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import compute_content_hash
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId

pytestmark = pytest.mark.integration


class _RecordingBackend:
    def __init__(self, dimension: int = 4) -> None:
        self.dimension = dimension
        self.calls: list[tuple[str, ...]] = []

    def embed(
        self,
        texts: Sequence[str],
        *,
        batch_size: int,
    ) -> Sequence[Sequence[float]]:
        self.calls.append(tuple(texts))
        return tuple(
            tuple(float(index) for index in range(self.dimension)) for _ in texts
        )


class _Factory:
    def __init__(self, backend: EmbeddingBackend, *, fail_local: bool = False) -> None:
        self.backend = backend
        self.fail_local = fail_local
        self.cache_dirs: list[str] = []

    def __call__(
        self,
        *,
        model_name: str,
        cache_dir: str,
        threads: int | None,
        local_files_only: bool,
    ) -> EmbeddingBackend:
        self.cache_dirs.append(cache_dir)
        if self.fail_local and local_files_only:
            raise RuntimeError("missing local model")
        return self.backend


def _chunk() -> Chunk:
    document_id = DocumentId("document-01")
    text = "cache dir note"
    return Chunk(
        id=ChunkId.from_parts(document_id, ("Note",), 1, 0),
        document_id=document_id,
        text=text,
        heading_path=("Note",),
        chunk_index=0,
        char_range=CharRange(0, len(text)),
        token_count=3,
        content_hash=compute_content_hash(text),
        heading_line=0,
        heading_occurrence=1,
    )


def test_fastembed_uses_embeddings_dir_under_data_dir(tmp_path: Path) -> None:
    layout = ensure_layout(tmp_path)
    backend = _RecordingBackend()
    factory = _Factory(backend)
    adapter = FastEmbedAdapter(
        model_id="intfloat/multilingual-e5-large",
        cache_dir=layout.embeddings,
        allow_download=False,
        backend_factory=factory,
        dimension_resolver=lambda _: 4,
    )

    vectors = adapter.embed_documents((_chunk(),))

    assert len(vectors) == 1
    assert factory.cache_dirs == [str(layout.embeddings.resolve())]
    assert str(layout.embeddings).startswith(str(layout.root))


def test_fastembed_unavailable_when_local_cache_empty(tmp_path: Path) -> None:
    layout = ensure_layout(tmp_path)
    factory = _Factory(_RecordingBackend(), fail_local=True)
    adapter = FastEmbedAdapter(
        model_id="intfloat/multilingual-e5-large",
        cache_dir=layout.embeddings,
        allow_download=False,
        backend_factory=factory,
        dimension_resolver=lambda _: 4,
    )

    with pytest.raises(EmbeddingModelUnavailableError):
        adapter.embed_query("offline query")
