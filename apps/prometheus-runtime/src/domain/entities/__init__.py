"""Public domain entities."""

from domain.entities.chunk import CharRange, Chunk
from domain.entities.document import Document, compute_content_hash, normalize_content
from domain.entities.grounded_answer import GroundedAnswer
from domain.entities.search_hit import SearchHit, sort_by_score

__all__ = [
    "CharRange",
    "Chunk",
    "Document",
    "GroundedAnswer",
    "SearchHit",
    "compute_content_hash",
    "normalize_content",
    "sort_by_score",
]
