"""Full Vault reindex orchestration through job-related ports."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from application.dto.index_fingerprint import IndexFingerprint
from application.dto.indexing import IndexingProgress, ReindexResult
from application.dto.job import Job, JobKind, JobStatus
from application.ports.cancellation import CancellationToken
from application.ports.index_rebuild import IndexRebuildWorkspace
from application.ports.job_store import JobStore
from application.ports.progress_reporter import ProgressReporter
from domain.entities.document import Document
from domain.errors import PrometheusError
from domain.value_objects.vault_id import VaultId


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
    ) -> None:
        self._vault_id = vault_id
        self._workspace = rebuild_workspace
        self._fingerprint = active_fingerprint
        self._jobs = job_store
        self._progress = progress_reporter
        if progress_interval <= 0:
            raise ValueError("progress_interval must be positive")
        self._progress_interval = progress_interval

    async def execute(
        self,
        documents: Iterable[Document],
        *,
        cancellation: CancellationToken,
        job: Job | None = None,
    ) -> ReindexResult:
        batch = tuple(documents)
        now = datetime.now(UTC)
        if job is None:
            job = self._jobs.create(self._vault_id, JobKind.REINDEX)
        job = job.with_state(
            status=JobStatus.RUNNING,
            progress=0.0,
            total_documents=len(batch),
            updated_at=now,
        )
        self._jobs.update(job)
        processed_documents = 0
        processed_chunks = 0
        session = self._workspace.begin()
        try:
            for document in batch:
                if cancellation.is_cancelled():
                    session.discard()
                    job = job.with_state(
                        status=JobStatus.CANCELLED,
                        progress=_ratio(processed_documents, len(batch)),
                        processed_documents=processed_documents,
                        processed_chunks=processed_chunks,
                        updated_at=datetime.now(UTC),
                    )
                    self._jobs.update(job)
                    return ReindexResult(job, processed_documents, processed_chunks, cancelled=True)
                result = await session.index_document.execute(document, force=True)
                processed_documents += 1
                processed_chunks += result.created_chunks
                progress = IndexingProgress(
                    processed_documents,
                    len(batch),
                    processed_chunks,
                )
                if _should_report_progress(
                    processed_documents, len(batch), self._progress_interval
                ):
                    self._progress.report(job.id, progress)
                    job = job.with_state(
                        status=JobStatus.RUNNING,
                        progress=progress.ratio,
                        processed_documents=processed_documents,
                        total_documents=len(batch),
                        processed_chunks=processed_chunks,
                        updated_at=datetime.now(UTC),
                    )
                    self._jobs.update(job)
            session.index_metadata_store.save(self._fingerprint)
            session.promote()
            job = job.with_state(
                status=JobStatus.COMPLETED,
                progress=1.0,
                processed_documents=processed_documents,
                total_documents=len(batch),
                processed_chunks=processed_chunks,
                updated_at=datetime.now(UTC),
            )
            self._jobs.update(job)
            return ReindexResult(job, processed_documents, processed_chunks, cancelled=False)
        except Exception as error:
            session.discard()
            code = error.code if isinstance(error, PrometheusError) else "REINDEX_FAILED"
            job = job.with_state(
                status=JobStatus.FAILED,
                progress=_ratio(processed_documents, len(batch)),
                processed_documents=processed_documents,
                total_documents=len(batch),
                processed_chunks=processed_chunks,
                updated_at=datetime.now(UTC),
                error=code,
            )
            self._jobs.update(job)
            raise


def _ratio(processed: int, total: int) -> float:
    return 1.0 if total == 0 else processed / total


def _should_report_progress(processed: int, total: int, interval: int) -> bool:
    if processed == total:
        return True
    return processed % interval == 0
