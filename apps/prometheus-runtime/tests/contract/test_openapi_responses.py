"""OpenAPI contract validation for localhost HTTP responses (PRM-82)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from adapters.inbound.http.app import create_app
from application.dto.indexing import IndexDocumentResult
from application.dto.runtime_status import IndexState, RuntimeStatus
from application.dto.search_result import SearchResult
from bootstrap.config import RuntimeSettings
from contract.openapi_schema import (
    assert_matches_schema,
    assert_schema_named,
    path_response_schema,
)
from domain.entities.grounded_answer import GroundedAnswer
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.source_reference import SourceReference
from fakes import FakeJobStore, FakeLanguageModel

pytestmark = pytest.mark.contract

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


def _client() -> TestClient:
    document_id = DocumentId(DOCUMENT)
    runtime = SimpleNamespace(
        serialized_index_document=_AsyncValue(
            IndexDocumentResult(document_id, created_chunks=2, deleted_chunks=0)
        ),
        search_notes=_AsyncValue(
            (
                SearchResult(
                    document_id,
                    ChunkId("chunk-000001"),
                    RelativePath("Notes/One.md"),
                    "Heading",
                    "fragment",
                    0.9,
                    heading_line=2,
                    heading_occurrence=1,
                ),
            )
        ),
        answer_question=_AsyncValue(
            GroundedAnswer.create(
                text="grounded",
                sources=(
                    SourceReference.create(
                        RelativePath("Notes/One.md"),
                        "Heading",
                        heading_line=2,
                        heading_occurrence=1,
                    ),
                ),
                used_chunk_ids=(ChunkId("chunk-000001"),),
                insufficient_context=False,
            )
        ),
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
                reindex_required=False,
                reindex_reason=None,
            )
        ),
    )
    jobs = FakeJobStore()
    base = SimpleNamespace(
        settings=RuntimeSettings(session_token=SecretStr("test-token")),
        language_model=FakeLanguageModel(),
        job_store=jobs,
    )
    return TestClient(
        create_app(base, vault_registry=_Registry(runtime), job_store=jobs),
        base_url="http://127.0.0.1:8765",
    )


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-ID": "request-contract-01",
        "X-Prometheus-Plugin-Version": "0.1.0",
    }


def test_success_responses_match_openapi_schemas() -> None:
    client = _client()
    headers = _headers()

    health = client.get("/v1/health")
    status = client.get(f"/v1/status?vaultId={VAULT}", headers=headers)
    put = client.put(
        f"/v1/vaults/{VAULT}/documents/{DOCUMENT}",
        headers=headers,
        json={
            "path": "Notes/One.md",
            "content": "note",
            "revision": 1,
            "modified_at": NOW.isoformat(),
        },
    )
    search = client.post(
        f"/v1/vaults/{VAULT}/search",
        headers=headers,
        json={"query": "note", "limit": 5},
    )
    chat = client.post(
        f"/v1/vaults/{VAULT}/chat",
        headers=headers,
        json={"query": "What is in the note?", "limit": 5},
    )

    assert health.status_code == 200
    assert_matches_schema(health.json(), path_response_schema("/v1/health", "get", "200"))
    assert status.status_code == 200
    assert_schema_named(status.json(), "StatusResponse")
    assert put.status_code == 200
    assert_schema_named(put.json(), "IndexDocumentResponse")
    assert search.status_code == 200
    assert_schema_named(search.json(), "SearchResponse")
    assert chat.status_code == 200
    assert_schema_named(chat.json(), "ChatResponse")


def test_error_envelope_matches_openapi_schema() -> None:
    client = _client()

    unauthorized = client.post(f"/v1/vaults/{VAULT}/search", json={"query": "note"})
    assert unauthorized.status_code == 401
    assert_schema_named(unauthorized.json(), "ErrorEnvelope")

    invalid = client.post(
        f"/v1/vaults/{VAULT}/search",
        headers=_headers(),
        json={"limit": 5},
    )
    assert invalid.status_code == 422
    # FastAPI may return HTTPValidationError; error middleware maps some to envelope.
    body = invalid.json()
    if "error" in body:
        assert_schema_named(body, "ErrorEnvelope")
    else:
        assert_schema_named(body, "HTTPValidationError")
