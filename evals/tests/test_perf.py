"""Performance benchmark and baseline tests."""

from __future__ import annotations

from pathlib import Path

from prometheus_evals.perf.baseline import BaselineTolerance, compare_to_baseline
from prometheus_evals.perf.runner import run_perf_eval
from prometheus_evals.perf.stats import percentile

BASELINE = Path(__file__).resolve().parents[1] / "baselines" / "perf_baseline.json"


def test_percentile_interpolates() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5


def test_perf_smoke_produces_stage_timings(tmp_path: Path) -> None:
    report = run_perf_eval(data_dir=tmp_path / "perf", scale="small")
    assert report["stages"]["indexing"]["p50_seconds"] > 0
    assert report["index_size_bytes"] > 0


def test_baseline_compare_passes_for_matching_report() -> None:
    if not BASELINE.is_file():
        return
    import json

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    problems = compare_to_baseline(baseline, baseline, tolerance=BaselineTolerance())
    assert not problems
