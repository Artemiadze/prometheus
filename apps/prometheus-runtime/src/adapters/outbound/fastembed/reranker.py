"""Local FastEmbed cross-encoder implementation of the Reranker port."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Protocol, cast

from adapters.outbound.fastembed.errors import RerankerBatchError, RerankerModelUnavailableError
from domain.entities.search_hit import SearchHit, sort_by_score


class CrossEncoderBackend(Protocol):
    """Small internal seam around FastEmbed reranking for isolated unit tests."""

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        batch_size: int,
    ) -> Sequence[float]: ...


class CrossEncoderFactory(Protocol):
    def __call__(
        self,
        *,
        model_name: str,
        cache_dir: str,
        threads: int | None,
    ) -> CrossEncoderBackend: ...


class _FastEmbedCrossEncoder(Protocol):
    def rerank(
        self,
        query: str,
        documents: str | Sequence[str],
        batch_size: int = 64,
    ) -> object: ...


class _ProductionCrossEncoderBackend:
    def __init__(
        self,
        *,
        model_name: str,
        cache_dir: str,
        threads: int | None,
    ) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self._model = cast(
            _FastEmbedCrossEncoder,
            TextCrossEncoder(
                model_name=model_name,
                cache_dir=cache_dir,
                threads=threads,
            ),
        )

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        batch_size: int,
    ) -> Sequence[float]:
        raw_scores = self._model.rerank(query, documents, batch_size=batch_size)
        return tuple(float(value) for value in cast(Iterable[float], raw_scores))


def _production_cross_encoder_factory(
    *,
    model_name: str,
    cache_dir: str,
    threads: int | None,
) -> CrossEncoderBackend:
    return _ProductionCrossEncoderBackend(
        model_name=model_name,
        cache_dir=cache_dir,
        threads=threads,
    )


def _supported_model(model_id: str) -> None:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    supported = {item["model"].casefold() for item in TextCrossEncoder.list_supported_models()}
    if model_id.casefold() not in supported:
        raise RerankerModelUnavailableError()


class FastEmbedReranker:
    """Score query-document pairs locally and reorder retrieval candidates."""

    def __init__(
        self,
        *,
        model_id: str,
        cache_dir: Path,
        batch_size: int = 32,
        threads: int | None = None,
        allow_download: bool = False,
        backend_factory: CrossEncoderFactory = _production_cross_encoder_factory,
        model_validator: Callable[[str], None] = _supported_model,
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
            model_validator(model_id)
        except RerankerModelUnavailableError:
            raise
        except Exception as error:
            raise RerankerModelUnavailableError() from error
        self._backend: CrossEncoderBackend | None = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def rerank(self, query: str, hits: Sequence[SearchHit]) -> Sequence[SearchHit]:
        if not hits:
            return ()
        backend = self._get_backend()
        documents = tuple(hit.chunk.text for hit in hits)
        try:
            scores = backend.rerank(query, documents, batch_size=self._batch_size)
        except Exception as error:
            raise RerankerBatchError() from error
        if len(scores) != len(hits):
            raise RerankerBatchError()
        reranked = tuple(
            SearchHit(
                chunk=hit.chunk,
                score=float(score),
                dense_score=hit.dense_score,
                lexical_score=hit.lexical_score,
                rerank_score=float(score),
            )
            for hit, score in zip(hits, scores, strict=True)
        )
        return sort_by_score(reranked)

    def _get_backend(self) -> CrossEncoderBackend:
        if self._backend is not None:
            return self._backend
        try:
            backend = self._create_backend()
        except Exception as error:
            raise RerankerModelUnavailableError() from error
        self._backend = backend
        return backend

    def _create_backend(self) -> CrossEncoderBackend:
        return self._backend_factory(
            model_name=self._model_id,
            cache_dir=str(self._cache_dir),
            threads=self._threads,
        )
