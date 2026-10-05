"""Tests for SQLite FTS5 lexical index (PRM-89)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.outbound.sqlite.database import MetadataDatabase
from adapters.outbound.sqlite.lexical_index import build_fts_match_query
from application.services.indexing_transaction import replace_document_index
from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document, compute_content_hash
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.search_scope import SearchScope
from domain.value_objects.vault_id import VaultId
from fakes import FakeVectorIndex


def _document(*, path: str = "Notes/security.md", content: str = "Body") -> Document:
    return Document.create(
        id=DocumentId.from_relative_path(path),
        vault_id=VaultId("vault-01"),
        relative_path=path,
        content=content,
        revision=1,
        modified_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _chunk(document: Document, text: str, *, index: int = 0) -> Chunk:
    return Chunk(
        id=ChunkId.from_parts(document.id, ("Section",), 1, index),
        document_id=document.id,
        text=text,
        heading_path=("Section",),
        chunk_index=index,
        char_range=CharRange(0, len(text)),
        token_count=max(1, len(text.split())),
        content_hash=compute_content_hash(text),
        heading_line=0,
        heading_occurrence=1,
    )


def _index(database: MetadataDatabase, document: Document, *texts: str) -> None:
    chunks = tuple(_chunk(document, text, index=index) for index, text in enumerate(texts))
    vectors = tuple((float(index),) for index in range(len(chunks)))
    replace_document_index(
        document=document,
        chunks=chunks,
        vectors=vectors,
        indexed_at=datetime(2026, 1, 2, tzinfo=UTC),
        vector_index=FakeVectorIndex(),
        document_repository=database.documents,
        unit_of_work=database.unit_of_work(),
        lexical_index=database.lexical,
    )


def test_build_fts_match_query_escapes_operators() -> None:
    assert build_fts_match_query('CVE-2026-1234 AND "NEAR"') == (
        '"CVE-2026-1234" OR "AND" OR "NEAR"'
    )


def test_cve_query_finds_exact_token(tmp_path: Path) -> None:
    database = MetadataDatabase(tmp_path)
    document = _document(content="# Security\n")
    _index(database, document, "Fix for CVE-2026-1234 in kernel module.")
    hits = database.lexical.search("CVE-2026-1234", limit=5)
    assert hits
    assert "CVE-2026-1234" in hits[0].chunk.text
    database.close()


def test_profile_matches_split_friendly_content(tmp_path: Path) -> None:
    database = MetadataDatabase(tmp_path)
    document = _document(path="Notes/docker.md")
    _index(database, document, "Run docker compose --profile web for local stack.")
    hits = database.lexical.search("profile", limit=5)
    assert hits
    database.close()


def test_replace_document_removes_old_lexical_rows(tmp_path: Path) -> None:
    database = MetadataDatabase(tmp_path)
    document = _document()
    _index(database, document, "alpha token unique")
    updated = Document.create(
        id=document.id,
        vault_id=document.vault_id,
        relative_path=document.relative_path,
        content="Updated",
        revision=2,
        modified_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    _index(database, updated, "beta token only")
    assert database.lexical.search("alpha", limit=5) == ()
    assert database.lexical.search("beta", limit=5)
    database.close()


def test_search_respects_current_note_scope(tmp_path: Path) -> None:
    database = MetadataDatabase(tmp_path)
    doc_a = _document(path="Notes/a.md")
    doc_b = _document(path="Notes/b.md")
    _index(database, doc_a, "sharedterm in a")
    _index(database, doc_b, "sharedterm in b")
    scope = SearchScope.current_note("Notes/a.md")
    hits = database.lexical.search("sharedterm", limit=10, scope=scope)
    assert len(hits) == 1
    assert hits[0].chunk.document_id == doc_a.id
    database.close()


def test_update_document_path_changes_scope_filter(tmp_path: Path) -> None:
    database = MetadataDatabase(tmp_path)
    document = _document(path="Notes/old/name.md")
    _index(database, document, "relocatable token")
    database.lexical.update_document_path(document.id, RelativePath("Notes/new/name.md"))
    database.documents.update_path(document.id, RelativePath("Notes/new/name.md"))
    scope = SearchScope.current_note("Notes/new/name.md")
    assert database.lexical.search("relocatable", limit=5, scope=scope)
    database.close()


def test_empty_query_returns_no_hits(tmp_path: Path) -> None:
    database = MetadataDatabase(tmp_path)
    document = _document()
    _index(database, document, "content")
    assert database.lexical.search("   ", limit=5) == ()
    with pytest.raises(ValueError, match="limit"):
        database.lexical.search("content", limit=-1)
    database.close()
