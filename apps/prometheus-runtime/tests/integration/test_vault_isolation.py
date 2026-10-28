"""Integration coverage for storage and retrieval isolation between Vaults."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from adapters.inbound.http.app import create_app
from adapters.outbound.filesystem.data_dir import ensure_layout
from application.dto.index_status import IndexStatus
from application.errors import VaultMismatchError
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from bootstrap.container_registry import VaultContainerRegistry
from domain.entities.chunk import Chunk
from domain.entities.document import Document
from domain.entities.search_hit import SearchHit
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import SearchScope
from domain.value_objects.vault_id import VaultId
from fakes import FakeChunker, FakeEmbedder, FakeLanguageModel, FakeMarkdownParser
from fakes.fake_vector_index import FakeVectorIndex

NOW = datetime(2026, 1, 1, tzinfo=UTC)
DOCUMENT_ID = DocumentId("same-document-id")


def _container(tmp_path: Path, vault_id: VaultId, embedder: FakeEmbedder) -> Container:
    return Container(
        RuntimeSettings(data_dir=tmp_path, session_token=SecretStr("test-token")),
        ensure_layout(tmp_path),
        vault_id=vault_id,
        embedder_factory=lambda: embedder,
        markdown_parser_factory=FakeMarkdownParser,
        chunker_factory=FakeChunker,
        language_model_factory=FakeLanguageModel,
    )


def _document(vault_id: VaultId, content: str) -> Document:
    return Document.create(
        id=DOCUMENT_ID,
        vault_id=vault_id,
        relative_path="Notes/Private.md",
        content=content,
        revision=1,
        modified_at=NOW,
    )


def test_search_results_do_not_cross_vault_boundaries(tmp_path: Path) -> None:
    vault_a_id = VaultId("vault-a")
    vault_b_id = VaultId("vault-b")
    vault_a = _container(tmp_path, vault_a_id, FakeEmbedder())
    vault_b = _container(tmp_path, vault_b_id, FakeEmbedder())

    asyncio.run(vault_a.index_document.execute(_document(vault_a_id, "alpha secret")))
    asyncio.run(vault_b.index_document.execute(_document(vault_b_id, "bravo secret")))

    results_a = asyncio.run(vault_a.search_notes.execute("alpha", limit=10))
    results_b = asyncio.run(vault_b.search_notes.execute("bravo", limit=10))

    assert [result.text for result in results_a] == ["alpha secret"]
    assert [result.text for result in results_b] == ["bravo secret"]
    assert all("bravo" not in result.text for result in results_a)
    assert all("alpha" not in result.text for result in results_b)

    vault_a.close()
    vault_b.close()


class _LeakySharedIndex(FakeVectorIndex):
    """Shared index that intentionally ignores Vault boundaries when searching."""

    def __init__(self) -> None:
        super().__init__()
        self._vault_by_document: dict[DocumentId, VaultId] = {}

    def upsert(
        self,
        document: Document,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        self._vault_by_document[document.id] = document.vault_id
        super().upsert(document, chunks, vectors)

    def search(
        self,
        query_vector: Sequence[float],
        limit: int,
        scope: SearchScope | None = None,
    ) -> Sequence[SearchHit]:
        return super().search(query_vector, limit, scope)


class _GuardingIndex:
    """Defense-in-depth wrapper that keeps a leaky index vault-safe."""

    def __init__(self, inner: _LeakySharedIndex, vault_id: VaultId) -> None:
        self._inner = inner
        self._vault_id = vault_id

    @property
    def status(self) -> IndexStatus:
        return self._inner.status

    def upsert(
        self,
        document: Document,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        if document.vault_id != self._vault_id:
            raise VaultMismatchError()
        self._inner.upsert(document, chunks, vectors)

    def delete_by_ids(self, chunk_ids: Sequence[ChunkId]) -> None:
        self._inner.delete_by_ids(chunk_ids)

    def delete_by_document(self, document_id: DocumentId) -> None:
        self._inner.delete_by_document(document_id)

    def retrieve_vectors(self, chunk_ids: Sequence[ChunkId]) -> Mapping[str, Sequence[float]]:
        return self._inner.retrieve_vectors(chunk_ids)

    def update_document_path(
        self,
        document_id: DocumentId,
        relative_path: RelativePath,
    ) -> None:
        self._inner.update_document_path(document_id, relative_path)

    def search(
        self,
        query_vector: Sequence[float],
        limit: int,
        scope: SearchScope | None = None,
    ) -> Sequence[SearchHit]:
        hits = self._inner.search(query_vector, limit=max(limit * 4, 10), scope=scope)
        owned = {
            document_id
            for document_id, vault_id in self._inner._vault_by_document.items()
            if vault_id == self._vault_id
        }
        return tuple(hit for hit in hits if hit.chunk.document_id in owned)[:limit]


def test_guarded_wrapper_blocks_leaky_shared_index_cross_talk(tmp_path: Path) -> None:
    vault_a_id = VaultId("vault-a")
    vault_b_id = VaultId("vault-b")
    shared = _LeakySharedIndex()
    vault_a = Container(
        RuntimeSettings(data_dir=tmp_path),
        ensure_layout(tmp_path),
        vault_id=vault_a_id,
        embedder_factory=FakeEmbedder,
        vector_index_factory=lambda: _GuardingIndex(shared, vault_a_id),
        markdown_parser_factory=FakeMarkdownParser,
        chunker_factory=FakeChunker,
    )
    vault_b = Container(
        RuntimeSettings(data_dir=tmp_path),
        ensure_layout(tmp_path),
        vault_id=vault_b_id,
        embedder_factory=FakeEmbedder,
        vector_index_factory=lambda: _GuardingIndex(shared, vault_b_id),
        markdown_parser_factory=FakeMarkdownParser,
        chunker_factory=FakeChunker,
    )

    asyncio.run(vault_a.index_document.execute(_document(vault_a_id, "alpha secret")))
    asyncio.run(
        vault_b.index_document.execute(
            Document.create(
                id=DocumentId("other-document"),
                vault_id=vault_b_id,
                relative_path="Notes/Other.md",
                content="bravo secret",
                revision=1,
                modified_at=NOW,
            )
        )
    )

    results_a = asyncio.run(vault_a.search_notes.execute("secret", limit=10))
    results_b = asyncio.run(vault_b.search_notes.execute("secret", limit=10))

    assert [result.text for result in results_a] == ["alpha secret"]
    assert [result.text for result in results_b] == ["bravo secret"]

    vault_a.close()
    vault_b.close()


def test_http_search_is_isolated_per_vault_and_rejects_unsafe_vault_id(
    tmp_path: Path,
) -> None:
    layout = ensure_layout(tmp_path)
    settings = RuntimeSettings(data_dir=tmp_path, session_token=SecretStr("test-token"))
    base = Container(
        settings,
        layout,
        embedder_factory=FakeEmbedder,
        markdown_parser_factory=FakeMarkdownParser,
        chunker_factory=FakeChunker,
        language_model_factory=FakeLanguageModel,
    )
    registry = VaultContainerRegistry(base)
    client = TestClient(
        create_app(base, vault_registry=registry, job_store=base.job_store),
        base_url="http://127.0.0.1:8765",
    )
    headers = {
        "Authorization": "Bearer test-token",
        "X-Prometheus-Plugin-Version": "0.1.0",
    }
    payload_a = {
        "path": "Notes/Private.md",
        "content": "alpha secret from vault a",
        "revision": 1,
        "modified_at": NOW.isoformat(),
    }
    payload_b = {
        "path": "Notes/Private.md",
        "content": "bravo secret from vault b",
        "revision": 1,
        "modified_at": NOW.isoformat(),
    }

    put_a = client.put(
        "/v1/vaults/vault-a/documents/same-document-id",
        json=payload_a,
        headers=headers,
    )
    put_b = client.put(
        "/v1/vaults/vault-b/documents/same-document-id",
        json=payload_b,
        headers=headers,
    )
    search_a = client.post(
        "/v1/vaults/vault-a/search",
        json={"query": "alpha secret"},
        headers=headers,
    )
    search_b = client.post(
        "/v1/vaults/vault-b/search",
        json={"query": "bravo secret"},
        headers=headers,
    )
    invalid = client.post(
        "/v1/vaults/BAD/search",
        json={"query": "alpha"},
        headers=headers,
    )

    assert put_a.status_code == 200
    assert put_b.status_code == 200
    assert [item["text"] for item in search_a.json()["results"]] == ["alpha secret from vault a"]
    assert [item["text"] for item in search_b.json()["results"]] == ["bravo secret from vault b"]
    assert invalid.status_code == 400
    registry.close_all()
    base.close()
