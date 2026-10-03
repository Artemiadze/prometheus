"""Run end-to-end RAG evaluation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bootstrap.container import Container
from domain.entities.grounded_answer import GroundedAnswer

from prometheus_evals.dataset.loader import load_dataset
from prometheus_evals.dataset.models import EvalDataset
from prometheus_evals.harness.container import build_eval_container, index_dataset
from prometheus_evals.rag.metrics import (
    RagAggregateMetrics,
    RagQuestionScore,
    aggregate_scores,
    score_answer,
)
from prometheus_evals.report import REPORT_SCHEMA_VERSION, fingerprint_to_dict, write_json_report


@dataclass(frozen=True, slots=True)
class RagReport:
    schema_version: int
    dataset_id: str
    dataset_version: str
    llm_profile: str
    index_fingerprint: dict[str, Any]
    aggregate: RagAggregateMetrics
    questions: tuple[RagQuestionScore, ...]
    answers: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "run_parameters": {"llm_profile": self.llm_profile},
            "index_fingerprint": self.index_fingerprint,
            "aggregate": self.aggregate.to_dict(),
            "questions": [
                {
                    "question_id": item.question_id,
                    "kind": item.kind,
                    "citation_correct": item.citation_correct,
                    "unsupported": item.unsupported,
                    "correct_refusal": item.correct_refusal,
                    "false_refusal": item.false_refusal,
                }
                for item in self.questions
            ],
            "answers": list(self.answers),
        }


def run_rag_eval(
    dataset_path: Path,
    *,
    data_dir: Path,
    llm_profile: str = "offline-extractive",
    search_limit: int = 10,
) -> RagReport:
    dataset = load_dataset(dataset_path)
    container, vault_id = build_eval_container(data_dir)
    try:
        index_dataset(container, vault_id, dataset)
        return _evaluate_rag(
            container,
            dataset,
            llm_profile=llm_profile,
            search_limit=search_limit,
        )
    finally:
        container.close()


def _evaluate_rag(
    container: Container,
    dataset: EvalDataset,
    *,
    llm_profile: str,
    search_limit: int,
) -> RagReport:
    scores: list[RagQuestionScore] = []
    answers: list[dict[str, Any]] = []
    for question in dataset.questions:
        answer = asyncio.run(
            container.answer_question.execute(question.question, limit=search_limit)
        )
        scores.append(score_answer(question, answer))
        answers.append(_answer_record(question.id, answer))
    aggregate = aggregate_scores(tuple(scores))
    return RagReport(
        schema_version=REPORT_SCHEMA_VERSION,
        dataset_id=dataset.manifest.dataset_id,
        dataset_version=dataset.manifest.version,
        llm_profile=llm_profile,
        index_fingerprint=fingerprint_to_dict(container.active_index_fingerprint),
        aggregate=aggregate,
        questions=tuple(scores),
        answers=tuple(answers),
    )


def _answer_record(question_id: str, answer: GroundedAnswer) -> dict[str, Any]:
    return {
        "question_id": question_id,
        "insufficient_context": answer.insufficient_context,
        "text": answer.text,
        "sources": [
            {"path": source.relative_path.value, "heading": source.heading}
            for source in answer.sources
        ],
    }


def run_rag_eval_to_file(
    dataset_path: Path,
    output_path: Path,
    *,
    data_dir: Path,
) -> RagReport:
    report = run_rag_eval(dataset_path, data_dir=data_dir)
    write_json_report(output_path, report.to_dict())
    return report
