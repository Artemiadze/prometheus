"""Contract tests for PRM-E10 inbound HTTP routes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from fastapi.testclient import TestClient
from pydantic import SecretStr

from adapters.inbound.http.app import create_app
from application.dto.indexing import IndexDocumentResult, RemoveDocumentResult
from application.dto.job import JobStatus
from application.dto.runtime_status import IndexState, RuntimeStatus
from application.dto.search_result import SearchResult
from application.ports.cancellation import CancellationToken
from bootstrap.config import RuntimeSettings
from domain.entities.grounded_answer import GroundedAnswer
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.vault_id import VaultId
from fakes import FakeJobStore, FakeLanguageModel

NOW = datetime(2026, 1, 1, tzinfo=UTC)
VAULT = "vault-01"
DOCUMENT = "document-01"


@dataclass
class _AsyncValue[T]:
    value: T

    async def execute(self, *_: object, **__: object) -> T:
        return self.value


class _Registry:
    def __init__(self, runtime: object) -> None:
        self.runtime = runtime

    def get(self, _: object) -> object:
        return self.runtime


def _client(*, index_error: Exception | None = None) -> TestClient:
    document_id = DocumentId(DOCUMENT)
    runtime = SimpleNamespace(
        index_document=_AsyncValue(
            IndexDocumentResult(document_id, created_chunks=2, deleted_chunks=1)
        ),
        remove_document=_AsyncValue(RemoveDocumentResult(document_id, True, 2)),
        synchronize_vault=_AsyncValue(None),
        search_notes=_AsyncValue(
            (
                SearchResult(
                    document_id,
                    ChunkId("chunk-000001"),
                    RelativePath("Notes/One.md"),
                    "Heading",
                    "fragment",
                    0.9,
                ),
            )
        ),
        answer_question=_AsyncValue(
            GroundedAnswer.create(
                text="grounded",
                sources=(),
                used_chunk_ids=(),
                insufficient_context=True,
            )
        ),
        reindex_vault=_AsyncValue(None),
        runtime_status=_AsyncValue(
            RuntimeStatus(
                "0.1.0",
                IndexState.READY,
                True,
                "fake-model",
                1,
                2,
                NOW,
                100,
            )
        ),
    )
    if index_error is not None:
        runtime.index_document = _Raises(index_error)
    jobs = FakeJobStore()
    base = SimpleNamespace(
        settings=RuntimeSettings(session_token=SecretStr("test-token")),
        language_model=FakeLanguageModel(),
        job_store=jobs,
    )
    return TestClient(create_app(base, vault_registry=_Registry(runtime), job_store=jobs))


@dataclass
class _Raises:
    error: Exception

    async def execute(self, *_: object, **__: object) -> object:
        raise self.error


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "X-Request-ID": "request-01"}


def test_health_is_unprotected_and_all_protected_responses_echo_request_id() -> None:
    client = _client()

    health = client.get("/v1/health")
    status = client.get(f"/v1/status?vaultId={VAULT}", headers=_headers())

    assert health.status_code == 200
    assert status.status_code == 200
    assert status.headers["X-Request-ID"] == "request-01"
    assert status.json()["api_version"] == "0.1.0"


def test_protected_routes_reject_missing_token_with_error_envelope() -> None:
    response = _client().post(f"/v1/vaults/{VAULT}/search", json={"query": "query"})

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "UNAUTHORIZED",
        "message": "A valid session token is required",
        "request_id": response.headers["X-Request-ID"],
    }


def test_document_endpoints_map_request_and_chunk_statistics() -> None:
    client = _client()
    payload = {
        "path": "Notes/One.md",
        "content": "contents",
        "revision": 1,
        "modified_at": NOW.isoformat(),
    }

    put = client.put(f"/v1/vaults/{VAULT}/documents/{DOCUMENT}", json=payload, headers=_headers())
    delete = client.delete(f"/v1/vaults/{VAULT}/documents/{DOCUMENT}", headers=_headers())

    assert put.status_code == 200
    assert put.json()["created_chunks"] == 2
    assert put.json()["skipped"] is False
    assert delete.json() == {"document_id": DOCUMENT, "removed": True, "removed_chunks": 2}


def test_search_and_chat_follow_public_response_contracts() -> None:
    client = _client()

    search = client.post(f"/v1/vaults/{VAULT}/search", json={"query": "query"}, headers=_headers())
    chat = client.post(f"/v1/vaults/{VAULT}/chat", json={"query": "question"}, headers=_headers())

    assert search.json() == {
        "results": [
            {"path": "Notes/One.md", "heading": "Heading", "text": "fragment", "score": 0.9}
        ]
    }
    assert chat.json() == {"answer": "grounded", "sources": [], "insufficient_context": True}


def test_validation_and_application_errors_use_stable_envelopes() -> None:
    from application.errors import RevisionConflictError

    client = _client(index_error=RevisionConflictError())
    invalid = client.post(f"/v1/vaults/{VAULT}/search", json={}, headers=_headers())
    conflict = client.put(
        f"/v1/vaults/{VAULT}/documents/{DOCUMENT}",
        json={
            "path": "Notes/One.md",
            "content": "contents",
            "revision": 1,
            "modified_at": NOW.isoformat(),
        },
        headers=_headers(),
    )

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "REVISION_CONFLICT"


def test_models_and_unknown_jobs_are_exposed_without_internal_details() -> None:
    client = _client()

    models = client.get("/v1/models", headers=_headers())
    missing = client.get("/v1/jobs/job-999999", headers=_headers())

    assert models.json()["models"][0]["name"] == "fake-model"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_sync_starts_job_and_job_route_returns_state() -> None:
    client = _client()
    response = client.post(
        f"/v1/vaults/{VAULT}/sync/complete",
        json={"entries": []},
        headers=_headers(),
    )

    assert response.status_code == 202
    job = client.get(response.json()["status_url"], headers=_headers())
    assert job.status_code == 200
    assert job.json()["status"] in {JobStatus.RUNNING.value, JobStatus.COMPLETED.value}


def test_job_runner_deduplicates_reindex_until_cooperative_cancellation() -> None:
    from adapters.inbound.http.jobs import BackgroundJobRunner

    jobs = FakeJobStore()
    runner = BackgroundJobRunner(jobs)
    release = asyncio.Event()

    class BlockingReindex:
        async def execute(self, *_: object, **kwargs: object) -> None:
            token = cast(CancellationToken, kwargs["cancellation"])
            while not token.is_cancelled():
                await asyncio.sleep(0)
            release.set()

    runtime = SimpleNamespace(reindex_vault=BlockingReindex())

    async def run() -> None:
        first = runner.start_reindex(VaultId(VAULT), runtime, ())
        assert runner.start_reindex(VaultId(VAULT), runtime, ()).id == first.id
        await asyncio.sleep(0)
        assert runner.cancel(first.id)
        await release.wait()

    asyncio.run(run())
