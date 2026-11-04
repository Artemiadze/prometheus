"""Tests for content-hash embedding reuse."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from application.dto.chunk_fingerprint import ChunkFingerprint
from application.services.embedding_reuse import (
    fill_resolved_embeddings,
    resolve_reusable_embeddings,
)
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document, compute_content_hash
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId
from fakes.fake_vector_index import FakeVectorIndex

NOW = datetime(2026, 1, 1, tzinfo=UTC)
VAULT = VaultId("vault-01")
DOC = DocumentId("document-01")


def _chunk(text: str, index: int) -> Chunk:
    return Chunk(
        id=ChunkId.from_parts(DOC, ("H",), 0, index),
        document_id=DOC,
        text=text,
        heading_path=("H",),
        chunk_index=index,
        char_range=CharRange(0, len(text)),
        token_count=max(1, len(text.split())),
        content_hash=compute_content_hash(text),
        heading_line=0,
        heading_occurrence=1,
    )


def test_resolve_reuses_by_content_hash_across_index_shift() -> None:
    vectors = FakeVectorIndex()
    document = Document.create(
        id=DOC,
        vault_id=VAULT,
        relative_path="Notes/One.md",
        content="body",
        revision=1,
        modified_at=NOW,
    )
    old_a = _chunk("alpha", 0)
    old_b = _chunk("beta", 1)
    vectors.upsert(document, (old_a, old_b), ((1.0, 0.0), (0.0, 1.0)))

    # Insert a new first chunk; prior alpha/beta shift to indexes 1 and 2.
    new_chunks = (_chunk("gamma", 0), _chunk("alpha", 1), _chunk("beta", 2))
    fingerprints = (
        ChunkFingerprint(old_a.id, 0, old_a.content_hash),
        ChunkFingerprint(old_b.id, 1, old_b.content_hash),
    )

    resolved = resolve_reusable_embeddings(new_chunks, fingerprints, vectors)

    assert resolved.missing_chunks == (new_chunks[0],)
    assert resolved.missing_positions == (0,)
    assert resolved.vectors[1] == (1.0, 0.0)
    assert resolved.vectors[2] == (0.0, 1.0)


def test_fill_resolved_embeddings_merges_missing_slots() -> None:
    vectors = FakeVectorIndex()
    chunks = (_chunk("a", 0), _chunk("b", 1))
    resolved = resolve_reusable_embeddings(chunks, (), vectors)
    filled = fill_resolved_embeddings(resolved, ((0.5, 0.5), (0.2, 0.8)))
    assert filled == ((0.5, 0.5), (0.2, 0.8))


def test_fill_resolved_embeddings_rejects_length_mismatch() -> None:
    vectors = FakeVectorIndex()
    chunks = (_chunk("a", 0),)
    resolved = resolve_reusable_embeddings(chunks, (), vectors)
    with pytest.raises(ValueError, match="embedded vector count"):
        fill_resolved_embeddings(resolved, ())
