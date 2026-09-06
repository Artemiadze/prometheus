"""Local FastEmbed implementation of the Embedder port."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Protocol, cast

from adapters.outbound.fastembed.errors import (
    EmbeddingBatchError,
    EmbeddingDimensionMismatchError,
    EmbeddingModelUnavailableError,
)
from application.dto.embedding import EmbeddingFingerprint
from domain.entities.chunk import Chunk


class EmbeddingBackend(Protocol):
    """Small internal seam around FastEmbed for isolated unit tests."""

    def embed(
        self,
        texts: Sequence[str],
        *,
        batch_size: int,
    ) -> Sequence[Sequence[float]]: ...


class BackendFactory(Protocol):
    """Construct an embedding backend with explicit cache/network policy."""

    def __call__(
        self,
        *,
        model_name: str,
        cache_dir: str,
        threads: int | None,
        local_files_only: bool,
    ) -> EmbeddingBackend: ...


class _FastEmbedModel(Protocol):
    def embed(
        self,
        documents: str | Iterable[str],
        batch_size: int = 256,
        parallel: int | None = None,
    ) -> Iterable[Iterable[float]]: ...


class _ProductionBackend:
    def __init__(
        self,
        *,
        model_name: str,
        cache_dir: str,
        threads: int | None,
        local_files_only: bool,
    ) -> None:
        from fastembed import TextEmbedding

        self._model = cast(
            _FastEmbedModel,
            TextEmbedding(
                model_name=model_name,
                cache_dir=cache_dir,
                threads=threads,
                local_files_only=local_files_only,
            ),
        )

    def embed(
        self,
        texts: Sequence[str],
        *,
        batch_size: int,
    ) -> Sequence[Sequence[float]]:
        return tuple(
            tuple(float(value) for value in vector)
            for vector in self._model.embed(texts, batch_size=batch_size, parallel=None)
        )


def _production_backend_factory(
    *,
    model_name: str,
    cache_dir: str,
    threads: int | None,
    local_files_only: bool,
) -> EmbeddingBackend:
    return _ProductionBackend(
        model_name=model_name,
        cache_dir=cache_dir,
        threads=threads,
        local_files_only=local_files_only,
    )


def _fastembed_dimension(model_name: str) -> int:
    from fastembed import TextEmbedding

    return int(TextEmbedding.get_embedding_size(model_name))


def _model_prefixes(model_id: str) -> tuple[str, str]:
    if "e5" in model_id.casefold():
        return "passage: ", "query: "
    return "", ""


class FastEmbedAdapter:
    """Generate embeddings locally with bounded batches and explicit downloads."""

    provider = "fastembed"

    def __init__(
        self,
        *,
        model_id: str,
        cache_dir: Path,
        batch_size: int = 64,
        threads: int | None = None,
        allow_download: bool = False,
        backend_factory: BackendFactory = _production_backend_factory,
        dimension_resolver: Callable[[str], int] = _fastembed_dimension,
    ) -> None:
        if batch_size <= 0 or (threads is not None and threads <= 0):
            raise ValueError("batch_size and threads must be positive")
        self._model_id = model_id
        self._cache_dir = cache_dir.expanduser().resolve()
        self._cache_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._batch_size = batch_size
        self._threads = threads
        self._allow_download = allow_download
        self._backend_factory = backend_factory
        try:
            dimension = dimension_resolver(model_id)
        except Exception as error:
            raise EmbeddingModelUnavailableError() from error
        if dimension <= 0:
            raise EmbeddingModelUnavailableError()
        self._dimension = dimension
        self._document_prefix, self._query_prefix = _model_prefixes(model_id)
        self._backend: EmbeddingBackend | None = None

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def fingerprint(self) -> EmbeddingFingerprint:
        return EmbeddingFingerprint(self.provider, self.model_id, self.dimension)

    def embed_documents(self, chunks: Sequence[Chunk]) -> Sequence[Sequence[float]]:
        if not chunks:
            return ()
        backend = self._get_backend()
        vectors: list[tuple[float, ...]] = []
        for offset in range(0, len(chunks), self._batch_size):
            batch = chunks[offset : offset + self._batch_size]
            texts = tuple(f"{self._document_prefix}{chunk.text}" for chunk in batch)
            vectors.extend(
                self._embed_batch(
                    backend,
                    texts,
                    batch_index=offset // self._batch_size,
                    processed_count=offset,
                )
            )
        return tuple(vectors)

    def embed_query(self, text: str) -> Sequence[float]:
        backend = self._get_backend()
        vectors = self._embed_batch(
            backend,
            (f"{self._query_prefix}{text}",),
            batch_index=0,
            processed_count=0,
        )
        return vectors[0]

    def _get_backend(self) -> EmbeddingBackend:
        if self._backend is not None:
            return self._backend
        try:
            backend = self._create_backend(local_files_only=True)
        except Exception as local_error:
            if not self._allow_download:
                raise EmbeddingModelUnavailableError() from local_error
            try:
                backend = self._create_backend(local_files_only=False)
            except Exception as download_error:
                raise EmbeddingModelUnavailableError() from download_error
        self._backend = backend
        return backend

    def _create_backend(self, *, local_files_only: bool) -> EmbeddingBackend:
        return self._backend_factory(
            model_name=self.model_id,
            cache_dir=str(self._cache_dir),
            threads=self._threads,
            local_files_only=local_files_only,
        )

    def _embed_batch(
        self,
        backend: EmbeddingBackend,
        texts: Sequence[str],
        *,
        batch_index: int,
        processed_count: int,
    ) -> tuple[tuple[float, ...], ...]:
        try:
            generated = backend.embed(texts, batch_size=len(texts))
        except Exception as error:
            raise EmbeddingBatchError(batch_index, processed_count) from error
        if len(generated) != len(texts):
            raise EmbeddingBatchError(batch_index, processed_count)

        vectors = tuple(tuple(float(value) for value in vector) for vector in generated)
        for vector in vectors:
            if len(vector) != self.dimension:
                raise EmbeddingDimensionMismatchError(self.dimension, len(vector))
        return vectors
