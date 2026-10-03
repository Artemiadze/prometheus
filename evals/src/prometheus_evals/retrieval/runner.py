"""Run retrieval evaluation against an indexed eval corpus."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bootstrap.config import RetrievalMode
from bootstrap.container import Container

from prometheus_evals.dataset.loader import load_dataset
from prometheus_evals.dataset.models import EvalDataset, EvalQuestion
from prometheus_evals.harness.container import build_eval_container, index_dataset
from prometheus_evals.report import REPORT_SCHEMA_VERSION, fingerprint_to_dict, write_json_report
from prometheus_evals.retrieval.metrics import (
    collapse_document_ranks,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)

DEFAULT_K_VALUES = (1, 3, 5, 10)


@dataclass(frozen=True, slots=True)
class RetrievalQuestionResult:
    question_id: str
    ranked_hits: tuple[tuple[str, str | None, float], ...]
    recall: dict[int, float]
    reciprocal_rank: float
    ndcg: dict[int, float]


@dataclass(frozen=True, slots=True)
class RetrievalReport:
    schema_version: int
    dataset_id: str
    dataset_version: str
    embedder_profile: str
    k_values: tuple[int, ...]
    chunk_size: int
    chunk_overlap: int
    retrieval_mode: RetrievalMode
    index_fingerprint: dict[str, Any]
    aggregate: dict[str, float]
    questions: tuple[RetrievalQuestionResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "run_parameters": {
                "embedder_profile": self.embedder_profile,
                "k_values": list(self.k_values),
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
                "retrieval_mode": self.retrieval_mode,
            },
            "index_fingerprint": self.index_fingerprint,
            "aggregate": self.aggregate,
            "questions": [
                {
                    "question_id": item.question_id,
                    "ranked_hits": [
                        {"path": path, "heading": heading, "score": score}
                        for path, heading, score in item.ranked_hits
                    ],
                    "recall": {str(k): value for k, value in sorted(item.recall.items())},
                    "reciprocal_rank": item.reciprocal_rank,
                    "ndcg": {str(k): value for k, value in sorted(item.ndcg.items())},
                }
                for item in self.questions
            ],
        }


def run_retrieval_eval(
    dataset_path: Path,
    *,
    data_dir: Path,
    k_values: tuple[int, ...] = DEFAULT_K_VALUES,
    max_k: int = 10,
    embedder_profile: str = "offline-bow",
    chunk_size: int = 700,
    chunk_overlap: int = 80,
    retrieval_mode: RetrievalMode = "dense",
) -> RetrievalReport:
    dataset = load_dataset(dataset_path)
    container, vault_id = build_eval_container(
        data_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        retrieval_mode=retrieval_mode,
    )
    try:
        index_dataset(container, vault_id, dataset)
        return _evaluate_indexed(
            container,
            dataset,
            k_values=k_values,
            max_k=max_k,
            embedder_profile=embedder_profile,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            retrieval_mode=retrieval_mode,
        )
    finally:
        container.close()


def _evaluate_indexed(
    container: Container,
    dataset: EvalDataset,
    *,
    k_values: tuple[int, ...],
    max_k: int,
    embedder_profile: str,
    chunk_size: int,
    chunk_overlap: int,
    retrieval_mode: RetrievalMode,
) -> RetrievalReport:
    answerable = [q for q in dataset.questions if q.kind == "answerable"]
    results = [
        _evaluate_question(container, question, k_values=k_values, max_k=max_k)
        for question in answerable
    ]
    aggregate = _aggregate_metrics(results, k_values)
    return RetrievalReport(
        schema_version=REPORT_SCHEMA_VERSION,
        dataset_id=dataset.manifest.dataset_id,
        dataset_version=dataset.manifest.version,
        embedder_profile=embedder_profile,
        k_values=k_values,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        retrieval_mode=retrieval_mode,
        index_fingerprint=fingerprint_to_dict(container.active_index_fingerprint),
        aggregate=aggregate,
        questions=tuple(results),
    )


def _evaluate_question(
    container: Container,
    question: EvalQuestion,
    *,
    k_values: tuple[int, ...],
    max_k: int,
) -> RetrievalQuestionResult:
    hits = asyncio.run(container.search_notes.execute(question.question, limit=max_k))
    ranked_raw = [(hit.relative_path.value, hit.heading, hit.score) for hit in hits]
    ranked_pairs = [(path, heading) for path, heading, _score in ranked_raw]
    expected = tuple((source.path, source.heading) for source in question.expected_sources)
    collapsed_docs = collapse_document_ranks(ranked_pairs)
    relevant_paths = {path for path, _ in expected}
    recall = {k: recall_at_k(expected, ranked_pairs, k) for k in k_values}
    rr = reciprocal_rank(relevant_paths, collapsed_docs)
    ndcg = {k: ndcg_at_k(relevant_paths, collapsed_docs, k) for k in k_values}
    return RetrievalQuestionResult(
        question_id=question.id,
        ranked_hits=tuple(ranked_raw),
        recall=recall,
        reciprocal_rank=rr,
        ndcg=ndcg,
    )


def _aggregate_metrics(
    results: Sequence[RetrievalQuestionResult],
    k_values: tuple[int, ...],
) -> dict[str, float]:
    if not results:
        return {}
    count = float(len(results))
    aggregate: dict[str, float] = {"mrr": sum(item.reciprocal_rank for item in results) / count}
    for k in k_values:
        aggregate[f"recall@{k}"] = sum(item.recall[k] for item in results) / count
        aggregate[f"ndcg@{k}"] = sum(item.ndcg[k] for item in results) / count
    return aggregate


def run_retrieval_eval_to_file(
    dataset_path: Path,
    output_path: Path,
    *,
    data_dir: Path,
    k_values: tuple[int, ...] = DEFAULT_K_VALUES,
) -> RetrievalReport:
    report = run_retrieval_eval(dataset_path, data_dir=data_dir, k_values=k_values)
    write_json_report(output_path, report.to_dict())
    return report
