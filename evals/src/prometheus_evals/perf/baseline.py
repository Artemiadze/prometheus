"""Compare performance reports against committed baselines."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class BaselineTolerance:
    latency_multiplier: float = 1.5
    ram_multiplier: float = 1.5
    index_size_multiplier: float = 1.2


def load_baseline(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("baseline JSON must be an object")
    return payload


def compare_to_baseline(
    report: dict[str, Any],
    baseline: dict[str, Any],
    *,
    tolerance: BaselineTolerance | None = None,
) -> list[str]:
    tol = tolerance or BaselineTolerance()
    problems: list[str] = []
    report_stages = report.get("stages", {})
    baseline_stages = baseline.get("stages", {})
    for stage in ("indexing", "retrieval", "reranking", "generation"):
        _compare_stage(
            problems, stage, report_stages.get(stage, {}), baseline_stages.get(stage, {}), tol
        )
    _compare_scalar(
        problems,
        "peak_rss_mb",
        float(report.get("peak_rss_mb", 0)),
        float(baseline.get("peak_rss_mb", 0)),
        tol.ram_multiplier,
    )
    _compare_scalar(
        problems,
        "index_size_bytes",
        float(report.get("index_size_bytes", 0)),
        float(baseline.get("index_size_bytes", 0)),
        tol.index_size_multiplier,
    )
    return problems


def _compare_stage(
    problems: list[str],
    stage: str,
    report: dict[str, Any],
    baseline: dict[str, Any],
    tolerance: BaselineTolerance,
) -> None:
    for metric in ("p50_seconds", "p95_seconds"):
        _compare_scalar(
            problems,
            f"{stage}.{metric}",
            float(report.get(metric, 0)),
            float(baseline.get(metric, 0)),
            tolerance.latency_multiplier,
        )


def _compare_scalar(
    problems: list[str],
    label: str,
    actual: float,
    expected: float,
    multiplier: float,
) -> None:
    if expected <= 0:
        return
    limit = expected * multiplier
    if actual > limit:
        problems.append(
            f"{label}: {actual:.4f} exceeds baseline limit {limit:.4f} (baseline {expected:.4f})"
        )
