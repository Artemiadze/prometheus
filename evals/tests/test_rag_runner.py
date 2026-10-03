"""RAG eval integration tests."""

from __future__ import annotations

from pathlib import Path

from prometheus_evals.rag.runner import run_rag_eval

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "synthetic_v1"

MIN_CITATION_CORRECTNESS = 0.5


def test_rag_eval_meets_citation_threshold(tmp_path: Path) -> None:
    report = run_rag_eval(DATASET, data_dir=tmp_path / "rag")
    assert (
        report.aggregate.citation_correctness_rate >= MIN_CITATION_CORRECTNESS
    ), report.aggregate.to_dict()
    assert report.aggregate.correct_refusal_rate >= 0.5
