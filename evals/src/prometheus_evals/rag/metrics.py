"""Grounded-answer quality metrics for RAG evaluation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.entities.grounded_answer import GroundedAnswer
from domain.value_objects.source_reference import SourceReference

from prometheus_evals.dataset.models import EvalQuestion


@dataclass(frozen=True, slots=True)
class RagQuestionScore:
    question_id: str
    kind: str
    citation_correct: bool | None
    unsupported: bool | None
    correct_refusal: bool | None
    false_refusal: bool | None


def source_matches_expected(
    source: SourceReference,
    expected_paths: set[str],
    expected_headings: dict[str, set[str | None]],
) -> bool:
    path = source.relative_path.value
    if path not in expected_paths:
        return False
    headings = expected_headings.get(path, set())
    if None in headings:
        return True
    return source.heading in headings


def score_answer(question: EvalQuestion, answer: GroundedAnswer) -> RagQuestionScore:
    if question.kind == "unanswerable":
        correct = answer.insufficient_context
        return RagQuestionScore(
            question_id=question.id,
            kind=question.kind,
            citation_correct=None,
            unsupported=None,
            correct_refusal=correct,
            false_refusal=None,
        )

    expected_paths = {source.path for source in question.expected_sources}
    expected_headings: dict[str, set[str | None]] = {}
    for source in question.expected_sources:
        expected_headings.setdefault(source.path, set()).add(source.heading)

    if answer.insufficient_context:
        return RagQuestionScore(
            question_id=question.id,
            kind=question.kind,
            citation_correct=False,
            unsupported=None,
            correct_refusal=None,
            false_refusal=True,
        )

    sources_ok = bool(answer.sources) and all(
        source_matches_expected(source, expected_paths, expected_headings)
        for source in answer.sources
    )
    has_expected = any(
        source_matches_expected(source, expected_paths, expected_headings)
        for source in answer.sources
    )
    citation_correct = sources_ok and has_expected
    keywords = [word.casefold() for word in question.reference_keywords]
    context_text = answer.text.casefold()
    keyword_ok = not keywords or any(word in context_text for word in keywords)
    unsupported = not citation_correct or not keyword_ok or not answer.sources
    return RagQuestionScore(
        question_id=question.id,
        kind=question.kind,
        citation_correct=citation_correct,
        unsupported=unsupported,
        correct_refusal=None,
        false_refusal=False,
    )


@dataclass(frozen=True, slots=True)
class RagAggregateMetrics:
    citation_correctness_rate: float
    unsupported_answer_rate: float
    correct_refusal_rate: float
    false_refusal_rate: float

    def to_dict(self) -> dict[str, float]:
        return {
            "citation_correctness_rate": self.citation_correctness_rate,
            "unsupported_answer_rate": self.unsupported_answer_rate,
            "correct_refusal_rate": self.correct_refusal_rate,
            "false_refusal_rate": self.false_refusal_rate,
        }


def aggregate_scores(scores: tuple[RagQuestionScore, ...]) -> RagAggregateMetrics:
    answerable = [item for item in scores if item.kind == "answerable"]
    unanswerable = [item for item in scores if item.kind == "unanswerable"]

    citation = _rate(
        [item.citation_correct for item in answerable if item.citation_correct is not None]
    )
    non_refusal = [
        item.unsupported
        for item in answerable
        if item.unsupported is not None and not item.false_refusal
    ]
    unsupported = _rate(non_refusal)
    refusals = _rate(
        [item.correct_refusal for item in unanswerable if item.correct_refusal is not None]
    )
    false_refusals = _rate(
        [item.false_refusal for item in answerable if item.false_refusal is not None]
    )
    return RagAggregateMetrics(
        citation_correctness_rate=citation,
        unsupported_answer_rate=unsupported,
        correct_refusal_rate=refusals,
        false_refusal_rate=false_refusals,
    )


def _rate(values: Sequence[bool | None]) -> float:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return 0.0
    return sum(1 for value in filtered if value) / len(filtered)
