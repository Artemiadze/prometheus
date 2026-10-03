"""Hybrid retrieval must not regress dense metrics on the eval corpus."""

from __future__ import annotations

from pathlib import Path

from prometheus_evals.retrieval.runner import run_retrieval_eval

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "synthetic_v1"


def test_hybrid_retrieval_is_at_least_as_good_as_dense(tmp_path: Path) -> None:
    dense = run_retrieval_eval(
        DATASET,
        data_dir=tmp_path / "dense",
        retrieval_mode="dense",
    )
    hybrid = run_retrieval_eval(
        DATASET,
        data_dir=tmp_path / "hybrid",
        retrieval_mode="hybrid",
    )

    assert hybrid.aggregate["recall@10"] >= dense.aggregate["recall@10"] - 1e-9
    assert hybrid.aggregate["mrr"] >= dense.aggregate["mrr"] - 1e-9
    assert hybrid.aggregate["ndcg@10"] >= dense.aggregate["ndcg@10"] - 1e-9
