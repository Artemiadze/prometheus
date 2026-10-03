"""Timing and percentile helpers."""

from __future__ import annotations

from collections.abc import Sequence


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    if quantile <= 0:
        return min(values)
    if quantile >= 1:
        return max(values)
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight
