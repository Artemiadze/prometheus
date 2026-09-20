"""SQLite-backed global JobStore."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime

from adapters.outbound.sqlite.errors import wrap_driver_errors
from application.dto.job import Job, JobId, JobKind, JobStatus
from domain.value_objects.vault_id import VaultId

_INTERRUPTED = "JOB_INTERRUPTED"


class SqliteJobStore:
    """Persist background jobs in ``state/jobs.sqlite``."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    @wrap_driver_errors
    def create(self, vault_id: VaultId, kind: JobKind) -> Job:
        now = datetime.now(UTC)
        job = Job(
            id=JobId(f"job-{uuid.uuid4().hex}"),
            vault_id=vault_id,
            kind=kind,
            status=JobStatus.PENDING,
            progress=0.0,
            processed_documents=0,
            total_documents=0,
            processed_chunks=0,
            created_at=now,
            updated_at=now,
        )
        self._insert(job)
        return job

    @wrap_driver_errors
    def get(self, job_id: JobId) -> Job | None:
        row = self._connection.execute(
            """
            SELECT
                job_id, vault_id, kind, status, progress,
                processed_documents, total_documents, processed_chunks,
                error, created_at, updated_at
            FROM jobs WHERE job_id = ?
            """,
            (job_id.value,),
        ).fetchone()
        return None if row is None else _row_to_job(row)

    @wrap_driver_errors
    def update(self, job: Job) -> None:
        self._connection.execute(
            """
            UPDATE jobs SET
                status = ?,
                progress = ?,
                processed_documents = ?,
                total_documents = ?,
                processed_chunks = ?,
                error = ?,
                updated_at = ?
            WHERE job_id = ?
            """,
            (
                job.status.value,
                job.progress,
                job.processed_documents,
                job.total_documents,
                job.processed_chunks,
                job.error,
                job.updated_at.isoformat(),
                job.id.value,
            ),
        )

    @wrap_driver_errors
    def delete(self, job_id: JobId) -> None:
        self._connection.execute("DELETE FROM jobs WHERE job_id = ?", (job_id.value,))

    @wrap_driver_errors
    def find_active(self, vault_id: VaultId) -> Job | None:
        row = self._connection.execute(
            """
            SELECT
                job_id, vault_id, kind, status, progress,
                processed_documents, total_documents, processed_chunks,
                error, created_at, updated_at
            FROM jobs
            WHERE vault_id = ? AND status IN (?, ?)
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (vault_id.value, JobStatus.PENDING.value, JobStatus.RUNNING.value),
        ).fetchone()
        return None if row is None else _row_to_job(row)

    @wrap_driver_errors
    def recover_interrupted(self) -> int:
        now = datetime.now(UTC).isoformat()
        cursor = self._connection.execute(
            """
            UPDATE jobs SET
                status = ?,
                error = ?,
                updated_at = ?
            WHERE status IN (?, ?)
            """,
            (
                JobStatus.FAILED.value,
                _INTERRUPTED,
                now,
                JobStatus.PENDING.value,
                JobStatus.RUNNING.value,
            ),
        )
        return int(cursor.rowcount)

    def _insert(self, job: Job) -> None:
        self._connection.execute(
            """
            INSERT INTO jobs (
                job_id, vault_id, kind, status, progress,
                processed_documents, total_documents, processed_chunks,
                error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id.value,
                job.vault_id.value,
                job.kind.value,
                job.status.value,
                job.progress,
                job.processed_documents,
                job.total_documents,
                job.processed_chunks,
                job.error,
                job.created_at.isoformat(),
                job.updated_at.isoformat(),
            ),
        )


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=JobId(row["job_id"]),
        vault_id=VaultId(row["vault_id"]),
        kind=JobKind(row["kind"]),
        status=JobStatus(row["status"]),
        progress=float(row["progress"]),
        processed_documents=int(row["processed_documents"]),
        total_documents=int(row["total_documents"]),
        processed_chunks=int(row["processed_chunks"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        error=row["error"],
    )
