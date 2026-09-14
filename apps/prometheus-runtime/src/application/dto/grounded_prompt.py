"""A grounded prompt and the exact Vault context included in it."""

from __future__ import annotations

from dataclasses import dataclass

from domain.entities.chunk import Chunk
from domain.errors import InvariantViolationError
from domain.value_objects.source_reference import SourceReference


@dataclass(frozen=True, slots=True)
class GroundedPrompt:
    """Prompt text tied to only the chunks and sources sent to the LLM."""

    text: str
    included_chunks: tuple[Chunk, ...]
    sources: tuple[SourceReference, ...]
    token_count: int

    def __post_init__(self) -> None:
        chunks = tuple(self.included_chunks)
        sources = tuple(dict.fromkeys(self.sources))
        object.__setattr__(self, "included_chunks", chunks)
        object.__setattr__(self, "sources", sources)
        if not self.text.strip() or self.token_count <= 0:
            raise InvariantViolationError()
