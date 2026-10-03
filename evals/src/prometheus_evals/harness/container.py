"""Build a runtime Container wired for offline evaluation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from adapters.outbound.filesystem.data_dir import ensure_layout
from adapters.outbound.markdown.chunker import HeadingAwareChunker
from adapters.outbound.markdown.parser import ObsidianMarkdownParser
from adapters.outbound.markdown.token_counter import HeuristicTokenCounter
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId

from prometheus_evals.dataset.models import EvalDataset
from prometheus_evals.harness.chunker import EvalChunker
from prometheus_evals.harness.embedder import HashedBagOfWordsEmbedder
from prometheus_evals.harness.language_model import ExtractiveEvalLanguageModel

EvalVault = tuple[Container, VaultId]


def build_eval_container(
    data_dir: Path,
    *,
    chunk_size: int = 700,
    chunk_overlap: int = 80,
    embedder: HashedBagOfWordsEmbedder | None = None,
    language_model: ExtractiveEvalLanguageModel | None = None,
) -> EvalVault:
    vault_id = VaultId("eval-vault")
    layout = ensure_layout(data_dir)
    settings = RuntimeSettings(
        data_dir=data_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_allow_download=False,
    )
    embedder_instance = embedder or HashedBagOfWordsEmbedder()
    llm = language_model or ExtractiveEvalLanguageModel()
    parser = ObsidianMarkdownParser()
    token_counter = HeuristicTokenCounter()

    def build_chunker() -> EvalChunker:
        return EvalChunker(
            HeadingAwareChunker(
                max_tokens=chunk_size,
                overlap_tokens=chunk_overlap,
                token_counter=token_counter,
            )
        )

    container = Container(
        settings,
        layout,
        vault_id=vault_id,
        embedder_factory=lambda: embedder_instance,
        language_model_factory=lambda: llm,
        markdown_parser_factory=lambda: parser,
        chunker_factory=build_chunker,
        token_counter_factory=lambda: token_counter,
    )
    return container, vault_id


def index_dataset(container: Container, vault_id: VaultId, dataset: EvalDataset) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    async def _index_all() -> None:
        for document in dataset.documents:
            entity = Document.create(
                id=DocumentId.from_relative_path(document.relative_path),
                vault_id=vault_id,
                relative_path=document.relative_path,
                content=document.content,
                revision=1,
                modified_at=now,
            )
            await container.index_document.execute(entity)

    asyncio.run(_index_all())


def with_eval_container(
    data_dir: Path,
    dataset: EvalDataset,
    *,
    chunk_size: int = 700,
    chunk_overlap: int = 80,
    body: Callable[[Container], None],
) -> None:
    container, vault_id = build_eval_container(
        data_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    try:
        index_dataset(container, vault_id, dataset)
        body(container)
    finally:
        container.close()
