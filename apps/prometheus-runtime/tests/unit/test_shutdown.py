"""Tests for graceful HTTP lifespan shutdown."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import SecretStr

from adapters.inbound.http.app import create_app
from adapters.inbound.http.jobs import BackgroundJobRunner
from application.dto.job import JobKind, JobStatus
from bootstrap.config import RuntimeSettings
from domain.value_objects.vault_id import VaultId
from fakes.fake_job_store import FakeJobStore

VAULT = VaultId("vault-01")


def test_lifecycle_recovers_running_jobs_on_startup() -> None:
    jobs = FakeJobStore()
    job = jobs.create(VAULT, JobKind.REINDEX)
    jobs.update(
        job.with_state(
            status=JobStatus.RUNNING,
            progress=0.2,
            updated_at=datetime.now(UTC),
        )
    )
    base = SimpleNamespace(
        settings=RuntimeSettings(session_token=SecretStr("token")),
        close=lambda: None,
    )

    with TestClient(create_app(base, job_store=jobs), base_url="http://127.0.0.1:8765"):
        recovered = jobs.get(job.id)
        assert recovered is not None
        assert recovered.status is JobStatus.FAILED
        assert recovered.error == "JOB_INTERRUPTED"


def test_runner_shutdown_is_idempotent_for_completed_jobs() -> None:
    jobs = FakeJobStore()
    runner = BackgroundJobRunner(jobs)
    job = jobs.create(VAULT, JobKind.SYNC)
    jobs.update(
        job.with_state(
            status=JobStatus.COMPLETED,
            progress=1.0,
            updated_at=datetime.now(UTC),
        )
    )

    asyncio.run(runner.shutdown(0.1))

    finished = jobs.get(job.id)
    assert finished is not None
    assert finished.status is JobStatus.COMPLETED
