"""Smoke checks against FastEmbed metadata without downloading a model."""

from fastembed import TextEmbedding


def test_default_multilingual_model_has_expected_dimension() -> None:
    assert TextEmbedding.get_embedding_size("intfloat/multilingual-e5-large") == 1024
