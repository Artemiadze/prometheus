"""Unit tests for retrieval metrics."""

from __future__ import annotations

from prometheus_evals.retrieval.metrics import ndcg_at_k, recall_at_k, reciprocal_rank


def test_recall_at_k_counts_first_relevant_document() -> None:
    expected = (("notes/a.md", None),)
    ranked = [("notes/b.md", None), ("notes/a.md", None)]
    assert recall_at_k(expected, ranked, k=2) == 1.0
    assert recall_at_k(expected, ranked, k=1) == 0.0


def test_reciprocal_rank_and_ndcg() -> None:
    ranked = ["notes/b.md", "notes/a.md", "notes/c.md"]
    relevant = {"notes/a.md"}
    assert reciprocal_rank(relevant, ranked) == 0.5
    assert ndcg_at_k(relevant, ranked, k=3) > 0.0
