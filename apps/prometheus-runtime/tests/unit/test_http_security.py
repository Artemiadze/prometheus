"""Tests for browser and Host-header restrictions on the localhost API."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from adapters.inbound.http.app import create_app
from bootstrap.config import RuntimeSettings


def _client() -> TestClient:
    return TestClient(
        create_app(SimpleNamespace(settings=RuntimeSettings())),
        base_url="http://127.0.0.1:8765",
    )


def test_cross_origin_request_is_rejected_with_a_stable_error() -> None:
    response = _client().get("/v1/health", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CROSS_ORIGIN_FORBIDDEN"
    assert "access-control-allow-origin" not in response.headers


def test_request_with_an_untrusted_host_is_rejected() -> None:
    response = _client().get("/v1/health", headers={"Host": "evil.example"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNTRUSTED_HOST"


def test_loopback_request_without_origin_is_allowed() -> None:
    response = _client().get("/v1/health")

    assert response.status_code == 200
