"""Full Vault reindex orchestration through job-related ports."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from application.dto.index_fingerprint import IndexFingerprint
from application.dto.indexing import IndexDocumentResult, IndexingProgress, ReindexResult
from application.dto.job import Job, JobKind, JobStatus
from application.errors import DocumentTooLargeError, PathIgnoredError
from application.ports.cancellation import CancellationToken
from application.ports.index_rebuild import IndexRebuildWorkspace
from application.ports.job_store import JobStore
from application.ports.progress_reporter import ProgressReporter
from application.services.embedding_reuse import ResolvedEmbeddings
from application.use_cases.index_document import IndexDocument, PreparedDocumentIndex
from domain.entities.chunk import Chunk
from domain.entities.document import Document
from domain.errors import PrometheusError
from domain.value_objects.vault_id import VaultId

_LOGGER = logging.getLogger(__name__)
_SKIPPABLE_DOCUMENT_ERRORS = (DocumentTooLargeError, PathIgnoredError)


@dataclass
class _PendingWrite:
    prepared: PreparedDocumentIndex
    resolved: ResolvedEmbeddings
    vectors: list[Sequence[float] | None] = field(init=False)

    def __post_init__(self) -> None:
        self.vectors = list(self.resolved.vectors)

    @property
    def complete(self) -> bool:
        return all(vector is not None for vector in self.vectors)


class ReindexVault:
    def __init__(
        self,
        *,
        vault_id: VaultId,
        rebuild_workspace: IndexRebuildWorkspace,
        active_fingerprint: IndexFingerprint,
        job_store: JobStore,
        progress_reporter: ProgressReporter,
        progress_interval: int = 10,
        embedding_batch_size: int = 64,
    ) -> None:
        self._vault_id = vault_id
        self._workspace = rebuild_workspace
        self._fingerprint = active_fingerprint
        self._jobs = job_store
        self._progress = progress_reporter
        if progress_interval <= 0:
            raise ValueError("progress_interval must be positive")
        if embedding_batch_size <= 0:
            raise ValueError("embedding_batch_size must be positive")
        self._progress_interval = progress_interval
        self._embedding_batch_size = embedding_batch_size

    async def execute(
        self,
        documents: Iterable[Document],
        *,
        cancellation: CancellationToken,
        job: Job | None = None,
    ) -> ReindexResult:
        batch = tuple(documents)
        now = datetime.now(UTC)
        active_job = job if job is not None else self._jobs.create(self._vault_id, JobKind.REINDEX)
        active_job = active_job.with_state(
            status=JobStatus.RUNNING,
            progress=0.0,
            total_documents=len(batch),
            updated_at=now,
        )
        self._jobs.update(active_job)
        processed_documents = 0
        processed_chunks = 0
        session = self._workspace.begin()
        indexer = session.index_document
        pending: list[_PendingWrite] = []
        embed_queue: list[tuple[_PendingWrite, int, Chunk]] = []

        async def flush_embeddings() -> None:
            nonlocal processed_documents, processed_chunks, active_job
            if not embed_queue:
                return
            chunks = tuple(chunk for _, _, chunk in embed_queue)
            embedded = await indexer.embed_batch(chunks)
            for (write, position, _), vector in zip(embed_queue, embedded, strict=True):
                write.vectors[position] = vector
            embed_queue.clear()
            processed_documents, processed_chunks, active_job = await _commit_completed(
                pending=pending,
                indexer=indexer,
                processed_documents=processed_documents,
                processed_chunks=processed_chunks,
                job=active_job,
                total=len(batch),
                progress_interval=self._progress_interval,
                jobs=self._jobs,
                progress=self._progress,
            )

        try:
            for document in batch:
                if cancellation.is_cancelled():
                    session.discard()
                    active_job = active_job.with_state(
                        status=JobStatus.CANCELLED,
                        progress=_ratio(processed_documents, len(batch)),
                        processed_documents=processed_documents,
                        processed_chunks=processed_chunks,
                        updated_at=datetime.now(UTC),
                    )
                    self._jobs.update(active_job)
                    return ReindexResult(
                        active_job, processed_documents, processed_chunks, cancelled=True
                    )
                try:
                    prepared = await indexer.prepare(document, force=True)
                except _SKIPPABLE_DOCUMENT_ERRORS as rejected:
                    _LOGGER.warning(
                        "reindex skipped document %s: %s", document.id.value, rejected.code
                    )
                    processed_documents += 1
                    continue
                if isinstance(prepared, IndexDocumentResult):
                    processed_documents += 1
                    processed_chunks += prepared.created_chunks
                    continue

                resolved = indexer.resolve_embeddings(prepared)
                write = _PendingWrite(prepared=prepared, resolved=resolved)
                pending.append(write)
                for position, chunk in zip(
                    resolved.missing_positions, resolved.missing_chunks, strict=True
                ):
                    embed_queue.append((write, position, chunk))
                    if len(embed_queue) >= self._embedding_batch_size:
                        await flush_embeddings()

            await flush_embeddings()
            processed_documents, processed_chunks, active_job = await _commit_completed(
                pending=pending,
                indexer=indexer,
                processed_documents=processed_documents,
                processed_chunks=processed_chunks,
                job=active_job,
                total=len(batch),
                progress_interval=self._progress_interval,
                jobs=self._jobs,
                progress=self._progress,
                force_all=True,
            )
            session.index_metadata_store.save(self._fingerprint)
            session.promote()
            active_job = active_job.with_state(
                status=JobStatus.COMPLETED,
                progress=1.0,
                processed_documents=processed_documents,
                total_documents=len(batch),
                processed_chunks=processed_chunks,
                updated_at=datetime.now(UTC),
            )
            self._jobs.update(active_job)
            return ReindexResult(active_job, processed_documents, processed_chunks, cancelled=False)
        except Exception as error:
            session.discard()
            code = error.code if isinstance(error, PrometheusError) else "REINDEX_FAILED"
            active_job = active_job.with_state(
                status=JobStatus.FAILED,
                progress=_ratio(processed_documents, len(batch)),
                processed_documents=processed_documents,
                total_documents=len(batch),
                processed_chunks=processed_chunks,
                updated_at=datetime.now(UTC),
                error=code,
            )
            self._jobs.update(active_job)
            raise


async def _commit_completed(
    *,
    pending: list[_PendingWrite],
    indexer: IndexDocument,
    processed_documents: int,
    processed_chunks: int,
    job: Job,
    total: int,
    progress_interval: int,
    jobs: JobStore,
    progress: ProgressReporter,
    force_all: bool = False,
) -> tuple[int, int, Job]:
    remaining: list[_PendingWrite] = []
    for write in pending:
        if not write.complete:
            if force_all:
                raise RuntimeError("reindex left unresolved embeddings")
            remaining.append(write)
            continue
        filled = tuple(vector for vector in write.vectors if vector is not None)
        if len(filled) != len(write.prepared.chunks):
            raise RuntimeError("reindex left unresolved embeddings")
        result = indexer.commit(write.prepared, filled)
        processed_documents += 1
        processed_chunks += result.created_chunks
        indexing_progress = IndexingProgress(
            processed_documents,
            total,
            processed_chunks,
        )
        if _should_report_progress(processed_documents, total, progress_interval):
            progress.report(job.id, indexing_progress)
            job = job.with_state(
                status=JobStatus.RUNNING,
                progress=indexing_progress.ratio,
                processed_documents=processed_documents,
                total_documents=total,
                processed_chunks=processed_chunks,
                updated_at=datetime.now(UTC),
            )
            jobs.update(job)
    pending[:] = remaining
    return processed_documents, processed_chunks, job


def _ratio(processed: int, total: int) -> float:
    return 1.0 if total == 0 else processed / total


def _should_report_progress(processed: int, total: int, interval: int) -> bool:
    if processed == total:
        return True
    return processed % interval == 0
