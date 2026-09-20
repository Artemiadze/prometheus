"""Full Vault reindex orchestration through job-related ports."""

from __future__ import annotations

from collections.abc import Iterable

from application.dto.index_fingerprint import IndexFingerprint
from application.dto.indexing import IndexingProgress, ReindexResult
from application.dto.job import Job, JobStatus
from application.ports.cancellation import CancellationToken
from application.ports.document_repository import DocumentRepository
from application.ports.index_metadata_store import IndexMetadataStore
from application.ports.job_store import JobStore
from application.ports.progress_reporter import ProgressReporter
from application.use_cases.index_document import IndexDocument
from application.use_cases.remove_document import RemoveDocument
from domain.entities.document import Document
from domain.errors import PrometheusError


class ReindexVault:
    def __init__(
        self,
        *,
        index_document: IndexDocument,
        remove_document: RemoveDocument,
        document_repository: DocumentRepository,
        index_metadata_store: IndexMetadataStore,
        active_fingerprint: IndexFingerprint,
        job_store: JobStore,
        progress_reporter: ProgressReporter,
    ) -> None:
        self._index = index_document
        self._remove = remove_document
        self._documents = document_repository
        self._metadata = index_metadata_store
        self._fingerprint = active_fingerprint
        self._jobs = job_store
        self._progress = progress_reporter

    async def execute(
        self,
        documents: Iterable[Document],
        *,
        cancellation: CancellationToken,
        job: Job | None = None,
    ) -> ReindexResult:
        batch = tuple(documents)
        job = self._jobs.create() if job is None else job
        job = Job(job.id, JobStatus.RUNNING, 0.0)
        self._jobs.update(job)
        processed_documents = 0
        processed_chunks = 0
        try:
            for state in self._documents.list_states():
                await self._remove.execute(state.document_id)
            for document in batch:
                if cancellation.is_cancelled():
                    job = Job(
                        job.id,
                        JobStatus.CANCELLED,
                        _ratio(processed_documents, len(batch)),
                    )
                    self._jobs.update(job)
                    return ReindexResult(job, processed_documents, processed_chunks, cancelled=True)
                result = await self._index.execute(document, force=True)
                processed_documents += 1
                processed_chunks += result.created_chunks
                progress = IndexingProgress(
                    processed_documents,
                    len(batch),
                    processed_chunks,
                )
                self._progress.report(job.id, progress)
                job = Job(job.id, JobStatus.RUNNING, progress.ratio)
                self._jobs.update(job)
            self._metadata.save(self._fingerprint)
            job = Job(job.id, JobStatus.COMPLETED, 1.0)
            self._jobs.update(job)
            return ReindexResult(job, processed_documents, processed_chunks, cancelled=False)
        except Exception as error:
            code = error.code if isinstance(error, PrometheusError) else "REINDEX_FAILED"
            job = Job(
                job.id,
                JobStatus.FAILED,
                _ratio(processed_documents, len(batch)),
                error=code,
            )
            self._jobs.update(job)
            raise


def _ratio(processed: int, total: int) -> float:
    return 1.0 if total == 0 else processed / total
