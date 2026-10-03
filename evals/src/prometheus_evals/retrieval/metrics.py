"""Information-retrieval metrics for ranked search hits."""

from __future__ import annotations

import math
from collections.abc import Sequence


def is_hit_relevant(
    path: str,
    heading: str | None,
    expected: Sequence[tuple[str, str | None]],
) -> bool:
    for exp_path, exp_heading in expected:
        if path != exp_path:
            continue
        if exp_heading is None or exp_heading == heading:
            return True
    return False


def collapse_document_ranks(hits: Sequence[tuple[str, str | None]]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for path, _heading in hits:
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


def recall_at_k(
    expected: Sequence[tuple[str, str | None]],
    ranked_raw: Sequence[tuple[str, str | None]],
    k: int,
) -> float:
    expected_paths = {path for path, _ in expected}
    if not expected_paths:
        return 0.0
    seen: set[str] = set()
    found: set[str] = set()
    for path, heading in ranked_raw:
        if path in seen:
            continue
        seen.add(path)
        if len(seen) > k:
            break
        if is_hit_relevant(path, heading, expected):
            found.add(path)
    return len(found & expected_paths) / len(expected_paths)


def reciprocal_rank(relevant_paths: set[str], ranked_docs: Sequence[str]) -> float:
    for index, path in enumerate(ranked_docs, start=1):
        if path in relevant_paths:
            return 1.0 / index
    return 0.0


def ndcg_at_k(relevant_paths: set[str], ranked_docs: Sequence[str], k: int) -> float:
    dcg = 0.0
    for index, path in enumerate(ranked_docs[:k], start=1):
        if path in relevant_paths:
            dcg += 1.0 / math.log2(index + 1)
    ideal = min(len(relevant_paths), k)
    if ideal == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal + 1))
    return dcg / idcg if idcg else 0.0
