"""In-process background-job runner until persistent PRM-E11 jobs exist."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine, Iterable
from dataclasses import dataclass

from adapters.inbound.http.dependencies import VaultRuntime
from application.dto.job import Job, JobId, JobStatus
from application.dto.vault_sync import VaultSnapshot
from application.ports.job_store import JobStore
from domain.entities.document import Document
from domain.errors import PrometheusError
from domain.value_objects.vault_id import VaultId


@dataclass(slots=True)
class InMemoryCancellationToken:
    """Cooperatively cancel a running reindex task."""

    cancelled: bool = False

    def is_cancelled(self) -> bool:
        return self.cancelled

    def cancel(self) -> None:
        self.cancelled = True


class BackgroundJobRunner:
    """Start, inspect, and cooperatively cancel process-local background jobs."""

    def __init__(self, job_store: JobStore) -> None:
        self._jobs = job_store
        self._tokens: dict[JobId, InMemoryCancellationToken] = {}
        self._tasks: dict[JobId, asyncio.Task[None]] = {}
        self._active_by_vault: dict[VaultId, JobId] = {}

    def start_sync(self, container: VaultRuntime, snapshot: VaultSnapshot) -> Job:
        job = self._start_job()

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
        active = self._active_by_vault.get(vault_id)
        if active is not None:
            job = self._jobs.get(active)
            if job is not None and job.status in {JobStatus.PENDING, JobStatus.RUNNING}:
                return job
        job = self._start_job()
        self._active_by_vault[vault_id] = job.id
        token = InMemoryCancellationToken()
        self._tokens[job.id] = token

        async def run() -> None:
            try:
                await container.reindex_vault.execute(documents, cancellation=token, job=job)
            except Exception as error:
                self._fail(job.id, error)
            finally:
                self._active_by_vault.pop(vault_id, None)
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
            self._jobs.update(Job(job_id, JobStatus.CANCELLED, job.progress))
            return True
        return False

    def _start_job(self) -> Job:
        pending = self._jobs.create()
        running = Job(pending.id, JobStatus.RUNNING, 0.0)
        self._jobs.update(running)
        return running

    def _schedule(self, job_id: JobId, coroutine: Coroutine[None, None, None]) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks[job_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(job_id, None))

    def _complete(self, job_id: JobId) -> None:
        job = self._jobs.get(job_id)
        if job is not None:
            self._jobs.update(Job(job_id, JobStatus.COMPLETED, 1.0))

    def _fail(self, job_id: JobId, error: Exception) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        code = error.code if isinstance(error, PrometheusError) else "JOB_FAILED"
        self._jobs.update(Job(job_id, JobStatus.FAILED, job.progress, error=code))
