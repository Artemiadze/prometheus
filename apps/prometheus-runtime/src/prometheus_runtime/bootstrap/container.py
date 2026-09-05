"""Composition root for application ports and concrete adapters."""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property

from prometheus_runtime.adapters.outbound.filesystem.data_dir import DataDirLayout
from prometheus_runtime.application.ports.document_repository import DocumentRepository
from prometheus_runtime.application.ports.embedder import Embedder
from prometheus_runtime.application.ports.language_model import LanguageModel
from prometheus_runtime.application.ports.vector_index import VectorIndex
from prometheus_runtime.bootstrap.config import RuntimeSettings
from prometheus_runtime.domain.errors import AdapterNotConfiguredError


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
        embedder_factory: Callable[[], Embedder] | None = None,
        vector_index_factory: Callable[[], VectorIndex] | None = None,
        language_model_factory: Callable[[], LanguageModel] | None = None,
        document_repository_factory: Callable[[], DocumentRepository] | None = None,
    ) -> None:
        self.settings = settings
        self.layout = layout
        self._embedder_factory = embedder_factory
        self._vector_index_factory = vector_index_factory
        self._language_model_factory = language_model_factory
        self._document_repository_factory = document_repository_factory

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
