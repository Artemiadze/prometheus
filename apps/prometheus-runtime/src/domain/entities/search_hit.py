"""Scored retrieval result."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

from domain.entities.chunk import Chunk
from domain.errors import InvariantViolationError


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A Chunk with its final and optional pipeline-stage scores."""

    chunk: Chunk
    score: float
    dense_score: float | None = None
    lexical_score: float | None = None
    rerank_score: float | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.score, bool)
            or not isinstance(self.score, (int, float))
            or not isfinite(self.score)
        ):
            raise InvariantViolationError()
        optional_scores = (self.dense_score, self.lexical_score, self.rerank_score)
        if any(
            value is not None
            and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            )
            for value in optional_scores
        ):
            raise InvariantViolationError()


def sort_by_score(hits: Iterable[SearchHit]) -> tuple[SearchHit, ...]:
    """Return a stable descending ordering by final score."""

    return tuple(sorted(hits, key=lambda hit: hit.score, reverse=True))
