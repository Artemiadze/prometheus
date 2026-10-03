"""Typer CLI for Prometheus evaluation runs."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Annotated

import typer

from prometheus_evals.perf.baseline import compare_to_baseline, load_baseline
from prometheus_evals.perf.runner import run_perf_eval_to_file
from prometheus_evals.rag.runner import run_rag_eval_to_file
from prometheus_evals.report import write_json_report
from prometheus_evals.retrieval.runner import run_retrieval_eval_to_file

app = typer.Typer(add_completion=False, no_args_is_help=True)

_DEFAULT_DATASET = Path(__file__).resolve().parents[2] / "datasets" / "synthetic_v1"
_DEFAULT_BASELINE = Path(__file__).resolve().parents[2] / "baselines" / "perf_baseline.json"


@app.command("retrieval")
def retrieval_command(
    output: Annotated[Path, typer.Option("--out", help="JSON report path")],
    dataset: Annotated[
        Path,
        typer.Option("--dataset", help="Dataset directory"),
    ] = _DEFAULT_DATASET,
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Runtime data directory"),
    ] = None,
) -> None:
    target = data_dir or Path(tempfile.mkdtemp(prefix="prometheus-evals-"))
    run_retrieval_eval_to_file(dataset, output, data_dir=target)
    typer.echo(f"Wrote retrieval report to {output}")


@app.command("rag")
def rag_command(
    output: Annotated[Path, typer.Option("--out", help="JSON report path")],
    dataset: Annotated[
        Path,
        typer.Option("--dataset", help="Dataset directory"),
    ] = _DEFAULT_DATASET,
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Runtime data directory"),
    ] = None,
) -> None:
    target = data_dir or Path(tempfile.mkdtemp(prefix="prometheus-evals-"))
    run_rag_eval_to_file(dataset, output, data_dir=target)
    typer.echo(f"Wrote RAG report to {output}")


@app.command("perf")
def perf_command(
    output: Annotated[Path, typer.Option("--out", help="JSON report path")],
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Runtime data directory"),
    ] = None,
    scale: Annotated[str, typer.Option("--scale", help="Corpus scale: small or full")] = "small",
    compare_baseline: Annotated[
        bool,
        typer.Option("--compare-baseline", help="Fail when metrics regress against baseline"),
    ] = False,
    baseline: Annotated[
        Path,
        typer.Option("--baseline", help="Baseline JSON path"),
    ] = _DEFAULT_BASELINE,
    update_baseline: Annotated[
        bool,
        typer.Option("--update-baseline", help="Overwrite baseline file with this run"),
    ] = False,
) -> None:
    target = data_dir or Path(tempfile.mkdtemp(prefix="prometheus-evals-perf-"))
    report = run_perf_eval_to_file(output, data_dir=target, scale=scale)
    if update_baseline:
        write_json_report(baseline, report)
        typer.echo(f"Updated baseline at {baseline}")
    if compare_baseline:
        problems = compare_to_baseline(report, load_baseline(baseline))
        if problems:
            for problem in problems:
                typer.echo(problem, err=True)
            raise typer.Exit(code=1)
    typer.echo(f"Wrote performance report to {output}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
    sys.exit(0)
