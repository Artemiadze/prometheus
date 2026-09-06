"""Tests for pre-write embedding fingerprint validation."""

import pytest

from application.dto.embedding import EmbeddingFingerprint
from application.errors import IndexRebuildRequiredError
from application.services.embedding_compatibility import ensure_embedding_compatible


def _fingerprint(
    *,
    provider: str = "fastembed",
    model_id: str = "intfloat/multilingual-e5-large",
    dimension: int = 1024,
) -> EmbeddingFingerprint:
    return EmbeddingFingerprint(provider, model_id, dimension)


def test_equal_embedding_fingerprints_are_compatible() -> None:
    fingerprint = _fingerprint()

    ensure_embedding_compatible(fingerprint, fingerprint)


@pytest.mark.parametrize(
    "actual",
    [
        _fingerprint(provider="other"),
        _fingerprint(model_id="other-model"),
        _fingerprint(dimension=384),
    ],
)
def test_any_embedding_mismatch_requires_rebuild(
    actual: EmbeddingFingerprint,
) -> None:
    with pytest.raises(IndexRebuildRequiredError) as caught:
        ensure_embedding_compatible(_fingerprint(), actual)

    assert caught.value.code == "INDEX_REBUILD_REQUIRED"


def test_dimension_mismatch_blocks_write_path() -> None:
    write_called = False

    def guarded_write() -> None:
        nonlocal write_called
        ensure_embedding_compatible(_fingerprint(), _fingerprint(dimension=384))
        write_called = True

    with pytest.raises(IndexRebuildRequiredError):
        guarded_write()

    assert not write_called
