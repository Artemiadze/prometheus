"""Performance benchmark for indexing, retrieval, and generation."""

from __future__ import annotations

import asyncio
import platform
import resource
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil
from bootstrap.container import Container
from domain.entities.document import Document
from domain.value_objects.document_id import DocumentId
from domain.value_objects.vault_id import VaultId

from prometheus_evals.dataset.models import DatasetManifest, EvalDataset
from prometheus_evals.harness.container import build_eval_container
from prometheus_evals.perf.corpus_generator import generate_perf_corpus
from prometheus_evals.perf.stats import percentile
from prometheus_evals.report import REPORT_SCHEMA_VERSION, fingerprint_to_dict, write_json_report

PerfScale = str


@dataclass(frozen=True, slots=True)
class StageTimings:
    p50_seconds: float
    p95_seconds: float

    def to_dict(self) -> dict[str, float]:
        return {"p50_seconds": self.p50_seconds, "p95_seconds": self.p95_seconds}


def run_perf_eval(
    *,
    data_dir: Path,
    scale: PerfScale = "small",
    seed: int = 42,
    retrieval_repeats: int = 20,
    generation_repeats: int = 10,
) -> dict[str, Any]:
    documents = generate_perf_corpus(scale=scale, seed=seed)
    dataset = EvalDataset(
        manifest=DatasetManifest(
            dataset_id=f"perf-{scale}",
            version="1",
            language_mix="en",
            description="Generated performance corpus",
        ),
        documents=documents,
        questions=(),
        root=str(data_dir),
    )
    process = psutil.Process()
    rss_before = process.memory_info().rss
    container, vault_id = build_eval_container(data_dir)
    peak_rss = rss_before
    fingerprint: dict[str, object] = {}
    chunk_count = 0
    try:
        index_seconds = _time_index(container, vault_id, dataset)
        peak_rss = max(peak_rss, process.memory_info().rss)
        query = _sample_query(documents[0].content)
        retrieval_samples = _time_retrieval(
            container,
            query=query,
            repeats=retrieval_repeats,
        )
        peak_rss = max(peak_rss, process.memory_info().rss)
        generation_samples = _time_generation(
            container,
            query=query,
            repeats=generation_repeats,
        )
        peak_rss = max(peak_rss, process.memory_info().rss)
        index_size = _directory_size(data_dir)
        chunk_count = container.index_statistics.read().chunk_count
        fingerprint = fingerprint_to_dict(container.active_index_fingerprint)
    finally:
        container.close()

    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "scale": scale,
        "seed": seed,
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": psutil.cpu_count(logical=True),
        },
        "index_fingerprint": fingerprint,
        "document_count": len(documents),
        "chunk_count": chunk_count,
        "stages": {
            "indexing": StageTimings(index_seconds, index_seconds).to_dict(),
            "retrieval": _stage_from_samples(retrieval_samples).to_dict(),
            "generation": _stage_from_samples(generation_samples).to_dict(),
        },
        "peak_rss_mb": (peak_rss - rss_before) / (1024 * 1024),
        "peak_rss_mb_total": peak_rss / (1024 * 1024),
        "index_size_bytes": index_size,
        "run_parameters": {
            "retrieval_repeats": retrieval_repeats,
            "generation_repeats": generation_repeats,
        },
    }
    return report


def _stage_from_samples(samples: list[float]) -> StageTimings:
    return StageTimings(
        p50_seconds=percentile(samples, 0.5),
        p95_seconds=percentile(samples, 0.95),
    )


def _time_index(container: Container, vault_id: VaultId, dataset: EvalDataset) -> float:
    from datetime import UTC, datetime

    now = datetime(2026, 1, 1, tzinfo=UTC)

    async def _index_all() -> None:
        for document in dataset.documents:
            entity = Document.create(
                id=DocumentId.from_relative_path(document.relative_path),
                vault_id=vault_id,
                relative_path=document.relative_path,
                content=document.content,
                revision=1,
                modified_at=now,
            )
            await container.index_document.execute(entity)

    start = time.perf_counter()
    asyncio.run(_index_all())
    return time.perf_counter() - start


def _time_retrieval(container: Container, *, query: str, repeats: int) -> list[float]:
    samples: list[float] = []
    for _ in range(repeats):

        async def _search() -> None:
            await container.search_notes.execute(query, limit=5)

        start = time.perf_counter()
        asyncio.run(_search())
        samples.append(time.perf_counter() - start)
    return samples[1:] if len(samples) > 1 else samples


def _time_generation(container: Container, *, query: str, repeats: int) -> list[float]:
    samples: list[float] = []
    for _ in range(repeats):

        async def _answer() -> None:
            await container.answer_question.execute(query, limit=5)

        start = time.perf_counter()
        asyncio.run(_answer())
        samples.append(time.perf_counter() - start)
    return samples[1:] if len(samples) > 1 else samples


def _sample_query(content: str) -> str:
    for line in content.splitlines():
        if "Marker token" in line:
            return "Marker token retrieval benchmarks"
    return "indexing chunking embeddings"


def _directory_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def run_perf_eval_to_file(output_path: Path, *, data_dir: Path, scale: PerfScale) -> dict[str, Any]:
    report = run_perf_eval(data_dir=data_dir, scale=scale)
    write_json_report(output_path, report)
    return report


def peak_rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # Linux reports ru_maxrss in kilobytes.
    return usage.ru_maxrss / 1024
