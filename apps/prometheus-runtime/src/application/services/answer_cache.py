"""In-process LRU cache for grounded answers."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from domain.entities.grounded_answer import GroundedAnswer
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.source_reference import SourceReference


@dataclass(frozen=True, slots=True)
class CachedAnswer:
    text: str
    sources: tuple[SourceReference, ...]
    used_chunk_ids: tuple[ChunkId, ...]
    insufficient_context: bool


class AnswerCache:
    def __init__(self, max_entries: int = 64) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._max_entries = max_entries
        self._entries: OrderedDict[str, CachedAnswer] = OrderedDict()

    def get(self, key: str) -> CachedAnswer | None:
        value = self._entries.get(key)
        if value is None:
            return None
        self._entries.move_to_end(key)
        return value

    def put(self, key: str, answer: GroundedAnswer) -> None:
        cached = CachedAnswer(
            text=answer.text,
            sources=answer.sources,
            used_chunk_ids=answer.used_chunk_ids,
            insufficient_context=answer.insufficient_context,
        )
        self._entries[key] = cached
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
