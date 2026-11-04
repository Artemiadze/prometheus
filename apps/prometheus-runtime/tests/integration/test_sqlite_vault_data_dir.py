"""Integration: SQLite metadata + sqlite-vec under a temporary data_dir."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.outbound.filesystem.data_dir import ensure_layout, vault_dir
from adapters.outbound.sqlite.database import MetadataDatabase
from application.dto.embedding import EmbeddingFingerprint
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document, compute_content_hash
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _document() -> Document:
    return Document.create(
        id=DocumentId("document-01"),
        vault_id=VaultId("vault-01"),
        relative_path="Notes/One.md",
        content="integration path storage",
        revision=1,
        modified_at=NOW,
    )


def _chunk(document: Document) -> Chunk:
    text = document.content
    return Chunk(
        id=ChunkId.from_parts(document.id, ("Section",), 1, 0),
        document_id=document.id,
        text=text,
        heading_path=("Section",),
        chunk_index=0,
        char_range=CharRange(0, len(text)),
        token_count=max(1, len(text.split())),
        content_hash=compute_content_hash(text),
        heading_line=0,
        heading_occurrence=1,
    )


def test_sqlite_vec_persists_under_data_dir_and_cleanup(tmp_path: Path) -> None:
    layout = ensure_layout(tmp_path)
    vault = vault_dir(layout, "vault-01")
    database = MetadataDatabase(vault)
    document = _document()
    chunk = _chunk(document)
    index = database.vector_index(
        vault_id=document.vault_id,
        embedding_fingerprint=EmbeddingFingerprint("fastembed", "test/model", 3),
    )
    try:
        index.upsert(document, (chunk,), ((1.0, 0.0, 0.0),))
        database.documents.save_indexed(document, (chunk,), NOW)
        hits = index.search((1.0, 0.0, 0.0), limit=5)
        assert hits[0].chunk.text == document.content
        index.delete_by_document(document.id)
        assert index.search((1.0, 0.0, 0.0), limit=5) == ()
    finally:
        database.close()

    assert (vault / "metadata.sqlite").is_file()
    assert not (vault / "qdrant").exists()
    assert layout.root == tmp_path.resolve()
