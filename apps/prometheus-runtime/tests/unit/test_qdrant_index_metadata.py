"""Tests for the Qdrant index compatibility sidecar."""

from pathlib import Path

import pytest

from adapters.outbound.qdrant.index_metadata import (
    IndexMetadata,
    read_index_metadata,
    write_index_metadata,
)
from application.dto.embedding import EmbeddingFingerprint


def test_metadata_round_trip_is_private(tmp_path: Path) -> None:
    path = tmp_path / "vault" / "qdrant_metadata.json"
    metadata = IndexMetadata(EmbeddingFingerprint("fastembed", "test/model", 3))

    write_index_metadata(path, metadata)

    assert read_index_metadata(path) == metadata
    assert path.stat().st_mode & 0o777 == 0o600


def test_missing_metadata_is_distinct_from_corrupted_metadata(tmp_path: Path) -> None:
    path = tmp_path / "qdrant_metadata.json"

    assert read_index_metadata(path) is None

    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError):
        read_index_metadata(path)
