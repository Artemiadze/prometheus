"""Domain events emitted while streaming a grounded chat answer."""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.source_reference import SourceReference


@dataclass(frozen=True, slots=True)
class AnswerTokenEvent:
    text: str


@dataclass(frozen=True, slots=True)
class AnswerCompletedEvent:
    sources: tuple[SourceReference, ...]
    insufficient_context: bool
