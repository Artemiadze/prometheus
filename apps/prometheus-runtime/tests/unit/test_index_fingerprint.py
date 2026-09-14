"""Tests for the full index fingerprint store and compatibility guard (PRM-40)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.outbound.sqlite.database import MetadataDatabase
from application.dto.embedding import EmbeddingFingerprint
from application.dto.index_fingerprint import IndexFingerprint
from application.errors import IndexRebuildRequiredError
from application.services.index_fingerprint import ensure_index_compatible


def _fingerprint(dimension: int = 4, chunk_size: int = 700) -> IndexFingerprint:
    return IndexFingerprint(
        embedding=EmbeddingFingerprint("fastembed", "test/model", dimension),
        parser_version=1,
        chunker_version=1,
        payload_schema_version=1,
        chunk_size=chunk_size,
        chunk_overlap=80,
    )


def test_fingerprint_round_trips_through_sqlite(tmp_path: Path) -> None:
    database = MetadataDatabase(tmp_path)
    fingerprint = _fingerprint()

    assert database.index_metadata.load() is None

    database.index_metadata.save(fingerprint)

    assert database.index_metadata.load() == fingerprint
    database.close()


def test_saving_again_overwrites_the_single_row(tmp_path: Path) -> None:
    database = MetadataDatabase(tmp_path)
    database.index_metadata.save(_fingerprint(dimension=4))

    database.index_metadata.save(_fingerprint(dimension=8))

    loaded = database.index_metadata.load()
    assert loaded is not None
    assert loaded.embedding.dimension == 8
    database.close()


def test_ensure_index_compatible_allows_the_first_run() -> None:
    ensure_index_compatible(None, _fingerprint())


def test_ensure_index_compatible_allows_a_matching_fingerprint() -> None:
    ensure_index_compatible(_fingerprint(), _fingerprint())


def test_ensure_index_compatible_requires_rebuild_on_dimension_change() -> None:
    with pytest.raises(IndexRebuildRequiredError):
        ensure_index_compatible(_fingerprint(dimension=4), _fingerprint(dimension=8))


def test_ensure_index_compatible_requires_rebuild_on_chunk_size_change() -> None:
    with pytest.raises(IndexRebuildRequiredError):
        ensure_index_compatible(_fingerprint(chunk_size=700), _fingerprint(chunk_size=500))
