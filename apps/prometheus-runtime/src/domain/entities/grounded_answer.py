"""Answer entity tied to the Vault sources actually used."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from domain.errors import InvariantViolationError
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.source_reference import SourceReference


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    """A non-empty answer with grounding state and ordered unique sources."""

    text: str
    sources: tuple[SourceReference, ...]
    used_chunk_ids: tuple[ChunkId, ...]
    insufficient_context: bool

    def __post_init__(self) -> None:
        unique_sources = tuple(dict.fromkeys(self.sources))
        unique_chunk_ids = tuple(dict.fromkeys(self.used_chunk_ids))
        object.__setattr__(self, "sources", unique_sources)
        object.__setattr__(self, "used_chunk_ids", unique_chunk_ids)

        if not self.text.strip() or (
            not self.insufficient_context and not unique_sources
        ):
            raise InvariantViolationError()

    @classmethod
    def create(
        cls,
        *,
        text: str,
        sources: Iterable[SourceReference] = (),
        used_chunk_ids: Iterable[ChunkId] = (),
        insufficient_context: bool,
    ) -> GroundedAnswer:
        return cls(
            text=text,
            sources=tuple(sources),
            used_chunk_ids=tuple(used_chunk_ids),
            insufficient_context=insufficient_context,
        )
