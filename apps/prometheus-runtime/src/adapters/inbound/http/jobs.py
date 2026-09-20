"""Persistent background-job runner with cooperative cancellation."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from adapters.inbound.http.dependencies import VaultRuntime
from application.dto.job import Job, JobId, JobKind, JobStatus
from application.dto.vault_sync import VaultSnapshot
from application.ports.job_store import JobStore
from domain.entities.document import Document
from domain.errors import PrometheusError
from domain.value_objects.vault_id import VaultId


@dataclass(slots=True)
class InMemoryCancellationToken:
    """Cooperatively cancel a running background task."""

    cancelled: bool = False

    def is_cancelled(self) -> bool:
        return self.cancelled

    def cancel(self) -> None:
        self.cancelled = True


class BackgroundJobRunner:
    """Start, inspect, cancel, and shut down background jobs."""

    def __init__(self, job_store: JobStore) -> None:
        self._jobs = job_store
        self._tokens: dict[JobId, InMemoryCancellationToken] = {}
        self._tasks: dict[JobId, asyncio.Task[None]] = {}
        self._shutting_down = False

    def start_sync(
        self, vault_id: VaultId, container: VaultRuntime, snapshot: VaultSnapshot
    ) -> Job:
        active = self._jobs.find_active(vault_id)
        if active is not None:
            return active
        job = self._start_job(vault_id, JobKind.SYNC)

        async def run() -> None:
            try:
                await container.synchronize_vault.execute(snapshot)
                self._complete(job.id)
            except Exception as error:
                self._fail(job.id, error)

        self._schedule(job.id, run())
        return job

    def start_reindex(
        self,
        vault_id: VaultId,
        container: VaultRuntime,
        documents: Iterable[Document],
    ) -> Job:
        active = self._jobs.find_active(vault_id)
        if active is not None:
            return active
        job = self._start_job(vault_id, JobKind.REINDEX)
        token = InMemoryCancellationToken()
        self._tokens[job.id] = token

        async def run() -> None:
            try:
                await container.reindex_vault.execute(
                    documents,
                    cancellation=token,
                    job=job,
                )
            except Exception as error:
                self._fail(job.id, error)
            finally:
                self._tokens.pop(job.id, None)

        self._schedule(job.id, run())
        return job

    def cancel(self, job_id: JobId) -> bool:
        job = self._jobs.get(job_id)
        if job is None or job.status not in {JobStatus.PENDING, JobStatus.RUNNING}:
            return False
        token = self._tokens.get(job_id)
        if token is not None:
            token.cancel()
            return True
        task = self._tasks.get(job_id)
        if task is not None:
            task.cancel()
            updated = job.with_state(
                status=JobStatus.CANCELLED,
                progress=job.progress,
                processed_documents=job.processed_documents,
                total_documents=job.total_documents,
                processed_chunks=job.processed_chunks,
                updated_at=datetime.now(UTC),
            )
            self._jobs.update(updated)
            return True
        return False

    async def shutdown(self, grace_seconds: float) -> None:
        """Cancel active jobs and wait for tasks to finish."""

        self._shutting_down = True
        for token in self._tokens.values():
            token.cancel()
        for task in list(self._tasks.values()):
            task.cancel()
        if self._tasks:
            await asyncio.wait(
                self._tasks.values(),
                timeout=max(0.0, grace_seconds),
            )
        for job_id in list(self._tasks):
            job = self._jobs.get(job_id)
            if job is not None and job.status in {JobStatus.PENDING, JobStatus.RUNNING}:
                self._jobs.update(
                    job.with_state(
                        status=JobStatus.FAILED,
                        progress=job.progress,
                        processed_documents=job.processed_documents,
                        total_documents=job.total_documents,
                        processed_chunks=job.processed_chunks,
                        updated_at=datetime.now(UTC),
                        error="JOB_INTERRUPTED",
                    )
                )

    def _start_job(self, vault_id: VaultId, kind: JobKind) -> Job:
        pending = self._jobs.create(vault_id, kind)
        running = pending.with_state(
            status=JobStatus.RUNNING,
            progress=0.0,
            updated_at=datetime.now(UTC),
        )
        self._jobs.update(running)
        return running

    def _schedule(self, job_id: JobId, coroutine: Coroutine[None, None, None]) -> None:
        if self._shutting_down:
            coroutine.close()
            return
        task = asyncio.create_task(coroutine)
        self._tasks[job_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(job_id, None))

    def _complete(self, job_id: JobId) -> None:
        job = self._jobs.get(job_id)
        if job is not None:
            self._jobs.update(
                job.with_state(
                    status=JobStatus.COMPLETED,
                    progress=1.0,
                    updated_at=datetime.now(UTC),
                )
            )

    def _fail(self, job_id: JobId, error: Exception) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        if job.status in {JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.FAILED}:
            return
        code = error.code if isinstance(error, PrometheusError) else "JOB_FAILED"
        self._jobs.update(
            job.with_state(
                status=JobStatus.FAILED,
                progress=job.progress,
                processed_documents=job.processed_documents,
                total_documents=job.total_documents,
                processed_chunks=job.processed_chunks,
                updated_at=datetime.now(UTC),
                error=code,
            )
        )
