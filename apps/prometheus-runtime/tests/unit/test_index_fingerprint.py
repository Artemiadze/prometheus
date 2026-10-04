"""Tests for the full index fingerprint store and compatibility guard (PRM-40 / PRM-74)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.outbound.filesystem.data_dir import ensure_layout
from adapters.outbound.sqlite.database import MetadataDatabase
from application.dto.embedding import EmbeddingFingerprint
from application.dto.index_fingerprint import IndexFingerprint
from application.errors import IndexRebuildRequiredError
from application.services.index_fingerprint import (
    describe_fingerprint_mismatch,
    ensure_index_compatible,
)
from bootstrap.config import RuntimeSettings
from bootstrap.container import Container
from fakes import FakeEmbedder


def _fingerprint(
    *,
    dimension: int = 4,
    chunk_size: int = 700,
    chunk_overlap: int = 80,
    model_id: str = "test/model",
    provider: str = "fastembed",
    parser_version: int = 1,
    chunker_version: int = 1,
    payload_schema_version: int = 2,
) -> IndexFingerprint:
    return IndexFingerprint(
        embedding=EmbeddingFingerprint(provider, model_id, dimension),
        parser_version=parser_version,
        chunker_version=chunker_version,
        payload_schema_version=payload_schema_version,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
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


@pytest.mark.parametrize(
    ("stored", "active", "marker"),
    [
        (_fingerprint(dimension=4), _fingerprint(dimension=8), r"embedding\.dimension"),
        (
            _fingerprint(model_id="old/model"),
            _fingerprint(model_id="new/model"),
            r"embedding\.model_id",
        ),
        (
            _fingerprint(provider="fastembed"),
            _fingerprint(provider="other"),
            r"embedding\.provider",
        ),
        (
            _fingerprint(parser_version=1),
            _fingerprint(parser_version=2),
            r"parser_version",
        ),
        (
            _fingerprint(chunker_version=1),
            _fingerprint(chunker_version=2),
            r"chunker_version",
        ),
        (
            _fingerprint(payload_schema_version=1),
            _fingerprint(payload_schema_version=2),
            r"payload_schema_version",
        ),
        (_fingerprint(chunk_size=700), _fingerprint(chunk_size=500), r"chunk_size"),
        (
            _fingerprint(chunk_overlap=80),
            _fingerprint(chunk_overlap=40),
            r"chunk_overlap",
        ),
    ],
)
def test_ensure_index_compatible_requires_rebuild_on_significant_change(
    stored: IndexFingerprint,
    active: IndexFingerprint,
    marker: str,
) -> None:
    with pytest.raises(IndexRebuildRequiredError, match=marker):
        ensure_index_compatible(stored, active)


def test_describe_fingerprint_mismatch_lists_all_changed_fields() -> None:
    message = describe_fingerprint_mismatch(
        _fingerprint(),
        _fingerprint(
            dimension=8,
            model_id="other/model",
            provider="other",
            parser_version=2,
            chunker_version=2,
            payload_schema_version=3,
            chunk_size=500,
            chunk_overlap=40,
        ),
    )

    assert "embedding.provider" in message
    assert "embedding.model_id" in message
    assert "embedding.dimension" in message
    assert "parser_version" in message
    assert "chunker_version" in message
    assert "payload_schema_version: 2 -> 3" in message
    assert "chunk_size" in message
    assert "chunk_overlap" in message


def test_llm_and_log_settings_do_not_affect_active_fingerprint(tmp_path: Path) -> None:
    layout = ensure_layout(tmp_path)
    left = Container(
        RuntimeSettings(data_dir=tmp_path, llm_model="qwen3:4b", log_level="INFO"),
        layout,
        vault_id=None,
        embedder_factory=FakeEmbedder,
    )
    right = Container(
        RuntimeSettings(
            data_dir=tmp_path,
            llm_model="llama3:8b",
            llm_temperature=0.9,
            log_level="DEBUG",
        ),
        layout,
        vault_id=None,
        embedder_factory=FakeEmbedder,
    )

    assert left.active_index_fingerprint == right.active_index_fingerprint
    left.close()
    right.close()
