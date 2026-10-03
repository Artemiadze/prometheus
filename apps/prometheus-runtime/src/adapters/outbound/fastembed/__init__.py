"""FastEmbed outbound adapter."""

from adapters.outbound.fastembed.adapter import FastEmbedAdapter
from adapters.outbound.fastembed.errors import (
    EmbeddingBatchError,
    EmbeddingDimensionMismatchError,
    EmbeddingModelUnavailableError,
    RerankerBatchError,
    RerankerModelUnavailableError,
)
from adapters.outbound.fastembed.reranker import FastEmbedReranker

__all__ = [
    "EmbeddingBatchError",
    "EmbeddingDimensionMismatchError",
    "EmbeddingModelUnavailableError",
    "FastEmbedAdapter",
    "FastEmbedReranker",
    "RerankerBatchError",
    "RerankerModelUnavailableError",
]
