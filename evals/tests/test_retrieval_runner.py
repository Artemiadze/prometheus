"""Retrieval eval integration and reproducibility."""

from __future__ import annotations

from pathlib import Path

from prometheus_evals.retrieval.runner import run_retrieval_eval

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "synthetic_v1"


def test_retrieval_eval_is_reproducible(tmp_path: Path) -> None:
    first = run_retrieval_eval(DATASET, data_dir=tmp_path / "run1")
    second = run_retrieval_eval(DATASET, data_dir=tmp_path / "run2")
    assert first.aggregate == second.aggregate


def test_retrieval_report_contains_fingerprint(tmp_path: Path) -> None:
    report = run_retrieval_eval(DATASET, data_dir=tmp_path / "run")
    assert "embedding" in report.index_fingerprint
    assert report.aggregate["recall@10"] >= 0.5
