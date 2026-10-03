"""Load and validate evaluation datasets from disk."""

from __future__ import annotations

import json
import re
from pathlib import Path

from prometheus_evals.dataset.models import (
    DatasetManifest,
    EvalDataset,
    EvalDocument,
    EvalQuestion,
    ExpectedSource,
)
from prometheus_evals.dataset.pii import assert_no_pii

_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


class DatasetValidationError(Exception):
    """Raised when a dataset fails structural or reference validation."""

    def __init__(self, problems: tuple[str, ...]) -> None:
        self.problems = problems
        message = "Dataset validation failed:\n" + "\n".join(f"  - {item}" for item in problems)
        super().__init__(message)


def load_dataset(path: Path) -> EvalDataset:
    root = path.expanduser().resolve()
    manifest_path = root / "manifest.json"
    questions_path = root / "questions.jsonl"
    notes_dir = root / "notes"

    problems: list[str] = []
    if not manifest_path.is_file():
        problems.append(f"missing manifest.json at {manifest_path}")
    if not questions_path.is_file():
        problems.append(f"missing questions.jsonl at {questions_path}")
    if not notes_dir.is_dir():
        problems.append(f"missing notes/ directory at {notes_dir}")
    if problems:
        raise DatasetValidationError(tuple(problems))

    manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    documents = _load_notes(notes_dir, problems)
    questions = _load_questions(questions_path, problems)
    if problems:
        raise DatasetValidationError(tuple(problems))

    dataset = EvalDataset(
        manifest=manifest,
        documents=tuple(documents),
        questions=tuple(questions),
        root=str(root),
    )
    _validate_references(dataset, problems)
    _validate_question_mix(dataset, problems)
    if problems:
        raise DatasetValidationError(tuple(problems))

    assert_no_pii(doc.content for doc in dataset.documents)
    assert_no_pii(q.question for q in dataset.questions)
    return dataset


def _load_notes(notes_dir: Path, problems: list[str]) -> list[EvalDocument]:
    documents: list[EvalDocument] = []
    for path in sorted(notes_dir.glob("**/*.md")):
        relative = path.relative_to(notes_dir).as_posix()
        documents.append(
            EvalDocument(
                relative_path=f"notes/{relative}", content=path.read_text(encoding="utf-8")
            )
        )
    if not documents:
        problems.append("notes/ contains no markdown files")
    return documents


def _load_questions(path: Path, problems: list[str]) -> list[EvalQuestion]:
    questions: list[EvalQuestion] = []
    seen_ids: set[str] = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
            question = EvalQuestion.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as error:
            problems.append(f"questions.jsonl line {line_no}: {error}")
            continue
        if question.id in seen_ids:
            problems.append(f"duplicate question id {question.id!r}")
        seen_ids.add(question.id)
        if question.kind == "unanswerable" and question.expected_sources:
            problems.append(
                f"question {question.id!r}: unanswerable must have empty expected_sources"
            )
        if question.kind == "answerable" and not question.expected_sources:
            problems.append(f"question {question.id!r}: answerable requires expected_sources")
        questions.append(question)
    return questions


def _validate_references(dataset: EvalDataset, problems: list[str]) -> None:
    by_path = {doc.relative_path: doc for doc in dataset.documents}
    for question in dataset.questions:
        for source in question.expected_sources:
            _validate_source_reference(source, by_path, question.id, problems)


def _validate_source_reference(
    source: ExpectedSource,
    by_path: dict[str, EvalDocument],
    question_id: str,
    problems: list[str],
) -> None:
    document = by_path.get(source.path)
    if document is None:
        problems.append(
            f"question {question_id!r}: expected_sources path {source.path!r} not in corpus"
        )
        return
    if source.heading is None:
        return
    headings = _extract_headings(document.content)
    if source.heading not in headings:
        problems.append(
            f"question {question_id!r}: heading {source.heading!r} not found in {source.path!r}"
        )


def _extract_headings(content: str) -> set[str]:
    return {match.group(1).strip() for match in _HEADING.finditer(content)}


def _validate_question_mix(dataset: EvalDataset, problems: list[str]) -> None:
    answerable = sum(1 for q in dataset.questions if q.kind == "answerable")
    unanswerable = sum(1 for q in dataset.questions if q.kind == "unanswerable")
    if answerable < 1:
        problems.append("dataset must include at least one answerable question")
    if unanswerable < 1:
        problems.append("dataset must include at least one unanswerable question")
