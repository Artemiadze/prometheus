"""HTTP tests for plugin version negotiation."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import SecretStr

from adapters.inbound.http.app import create_app
from adapters.inbound.http.version_gate import PLUGIN_VERSION_HEADER
from application.services.version_compatibility import COMPATIBLE_PLUGIN_RANGE
from bootstrap.config import RuntimeSettings
from fakes import FakeJobStore, FakeLanguageModel


def _client() -> TestClient:
    base = SimpleNamespace(
        settings=RuntimeSettings(session_token=SecretStr("test-token")),
        language_model=FakeLanguageModel(),
        job_store=FakeJobStore(),
    )
    return TestClient(create_app(base, job_store=base.job_store), base_url="http://127.0.0.1:8765")


def test_health_does_not_require_plugin_version() -> None:
    response = _client().get("/v1/health")
    assert response.status_code == 200


def test_incompatible_plugin_version_returns_stable_error() -> None:
    response = _client().get(
        "/v1/models",
        headers={
            "Authorization": "Bearer test-token",
            PLUGIN_VERSION_HEADER: "9.9.9",
        },
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "RUNTIME_VERSION_INCOMPATIBLE"
    assert "9.9.9" not in error["message"]
    assert COMPATIBLE_PLUGIN_RANGE in error["message"]


def test_missing_plugin_version_is_rejected() -> None:
    response = _client().get(
        "/v1/models",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUNTIME_VERSION_INCOMPATIBLE"


def test_compatible_plugin_version_is_accepted() -> None:
    response = _client().get(
        "/v1/models",
        headers={
            "Authorization": "Bearer test-token",
            PLUGIN_VERSION_HEADER: "0.1.0",
        },
    )
    assert response.status_code == 200


def test_prerelease_plugin_version_is_rejected_without_echoing_header() -> None:
    response = _client().get(
        "/v1/models",
        headers={
            "Authorization": "Bearer test-token",
            PLUGIN_VERSION_HEADER: "0.1.0-rc.1",
        },
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "RUNTIME_VERSION_INCOMPATIBLE"
    assert "0.1.0-rc.1" not in error["message"]
    assert "rc" not in error["message"]
