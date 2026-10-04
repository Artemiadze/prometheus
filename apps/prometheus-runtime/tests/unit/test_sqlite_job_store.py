"""Tests for persistent SQLite JobStore."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.outbound.sqlite.errors import MetadataStoreError
from adapters.outbound.sqlite.jobs_database import JobsDatabase
from application.dto.job import JobKind, JobStatus
from domain.value_objects.vault_id import VaultId

VAULT = VaultId("vault-01")


def test_jobs_persist_across_database_reopen(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    database = JobsDatabase(state_dir)
    job = database.job_store.create(VAULT, JobKind.REINDEX)
    job = job.with_state(
        status=JobStatus.RUNNING,
        progress=0.25,
        processed_documents=1,
        total_documents=4,
        processed_chunks=3,
        updated_at=datetime.now(UTC),
    )
    database.job_store.update(job)
    database.close()

    reopened = JobsDatabase(state_dir)
    loaded = reopened.job_store.get(job.id)
    reopened.close()

    assert loaded is not None
    assert loaded.status is JobStatus.RUNNING
    assert loaded.progress == 0.25
    assert loaded.processed_documents == 1


def test_only_one_active_job_per_vault(tmp_path: Path) -> None:
    database = JobsDatabase(tmp_path / "state")
    first = database.job_store.create(VAULT, JobKind.REINDEX)
    database.job_store.update(
        first.with_state(
            status=JobStatus.RUNNING, progress=0.0, updated_at=datetime.now(UTC)
        )
    )
    with pytest.raises(MetadataStoreError):
        second = database.job_store.create(VAULT, JobKind.SYNC)
        database.job_store.update(
            second.with_state(
                status=JobStatus.PENDING,
                progress=0.0,
                updated_at=datetime.now(UTC),
            )
        )
    database.close()


def test_recover_interrupted_marks_running_jobs_failed(tmp_path: Path) -> None:
    database = JobsDatabase(tmp_path / "state")
    job = database.job_store.create(VAULT, JobKind.REINDEX)
    database.job_store.update(
        job.with_state(
            status=JobStatus.RUNNING, progress=0.1, updated_at=datetime.now(UTC)
        )
    )
    database.close()

    reopened = JobsDatabase(tmp_path / "state")
    assert reopened.job_store.recover_interrupted() == 1
    recovered = reopened.job_store.get(job.id)
    reopened.close()

    assert recovered is not None
    assert recovered.status is JobStatus.FAILED
    assert recovered.error == "JOB_INTERRUPTED"
