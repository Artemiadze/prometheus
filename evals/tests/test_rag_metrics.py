"""RAG metric scoring tests."""

from __future__ import annotations

from domain.entities.grounded_answer import GroundedAnswer
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.source_reference import SourceReference

from prometheus_evals.dataset.models import EvalQuestion, ExpectedSource
from prometheus_evals.rag.metrics import score_answer


def test_score_answer_marks_correct_refusal() -> None:
    question = EvalQuestion(
        id="u1",
        question="Unknown?",
        kind="unanswerable",
        expected_sources=(),
        reference_keywords=(),
    )
    answer = GroundedAnswer.create(
        text="The notes do not contain enough information to answer this question.",
        insufficient_context=True,
    )
    score = score_answer(question, answer)
    assert score.correct_refusal is True


def test_score_answer_detects_false_refusal() -> None:
    question = EvalQuestion(
        id="a1",
        question="Q",
        kind="answerable",
        expected_sources=(ExpectedSource(path="notes/a.md"),),
        reference_keywords=("token",),
    )
    answer = GroundedAnswer.create(
        text="The notes do not contain enough information to answer this question.",
        insufficient_context=True,
    )
    score = score_answer(question, answer)
    assert score.false_refusal is True


def test_score_answer_citation_correctness() -> None:
    question = EvalQuestion(
        id="a2",
        question="Q",
        kind="answerable",
        expected_sources=(ExpectedSource(path="notes/a.md", heading="Facts"),),
        reference_keywords=("marker",),
    )
    answer = GroundedAnswer.create(
        text="marker answer",
        sources=(SourceReference(RelativePath("notes/a.md"), "Facts"),),
        used_chunk_ids=(),
        insufficient_context=False,
    )
    score = score_answer(question, answer)
    assert score.citation_correct is True
    assert score.unsupported is False
