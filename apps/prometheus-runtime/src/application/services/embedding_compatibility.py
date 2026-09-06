"""Compatibility guard for embedding-backed index writes."""

from application.dto.embedding import EmbeddingFingerprint
from application.errors import IndexRebuildRequiredError


def ensure_embedding_compatible(
    expected: EmbeddingFingerprint,
    actual: EmbeddingFingerprint,
) -> None:
    """Block vector writes when index and active model metadata differ."""

    if expected != actual:
        raise IndexRebuildRequiredError()
