"""Pure rules for selecting sufficiently grounded retrieval context."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite

from domain.entities.search_hit import SearchHit, sort_by_score
from domain.errors import InvariantViolationError
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.source_reference import SourceReference


@dataclass(frozen=True, slots=True)
class ContextSelection:
    """Ordered retrieval context and its sufficiency decision."""

    hits: tuple[SearchHit, ...]
    insufficient_context: bool


@dataclass(frozen=True, slots=True)
class GroundingPolicy:
    """Apply BR-4 score, count, and context-size constraints without IO."""

    min_score: float = 0.35
    min_relevant_chunks: int = 1
    max_context_chunks: int = 8

    def __post_init__(self) -> None:
        if (
            not isfinite(self.min_score)
            or self.min_relevant_chunks <= 0
            or self.max_context_chunks < self.min_relevant_chunks
        ):
            raise InvariantViolationError()

    def select_context(self, hits: Iterable[SearchHit]) -> ContextSelection:
        """Filter low-confidence hits, order them, and enforce the context budget."""

        relevant = (hit for hit in hits if hit.score >= self.min_score)
        selected = sort_by_score(relevant)[: self.max_context_chunks]
        return ContextSelection(
            hits=selected,
            insufficient_context=len(selected) < self.min_relevant_chunks,
        )

    def build_sources(
        self,
        hits: Iterable[SearchHit],
        document_paths: Mapping[DocumentId, RelativePath],
    ) -> tuple[SourceReference, ...]:
        """Build unique sources from chunks that pass this policy."""

        selection = self.select_context(hits)
        sources: list[SourceReference] = []
        for hit in selection.hits:
            try:
                path = document_paths[hit.chunk.document_id]
            except KeyError as exc:
                raise InvariantViolationError() from exc
            source = SourceReference.create(
                path,
                hit.chunk.heading,
                heading_line=hit.chunk.heading_line,
                heading_occurrence=hit.chunk.heading_occurrence,
            )
            if source not in sources:
                sources.append(source)
        return tuple(sources)
