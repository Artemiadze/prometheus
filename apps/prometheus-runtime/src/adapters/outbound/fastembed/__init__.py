"""FastEmbed outbound adapter."""

from adapters.outbound.fastembed.adapter import FastEmbedAdapter
from adapters.outbound.fastembed.errors import (
    EmbeddingBatchError,
    EmbeddingDimensionMismatchError,
    EmbeddingModelUnavailableError,
)

__all__ = [
    "EmbeddingBatchError",
    "EmbeddingDimensionMismatchError",
    "EmbeddingModelUnavailableError",
    "FastEmbedAdapter",
]
