"""Tests for the minimal HTTP application."""

from fastapi.testclient import TestClient

from adapters.inbound.http.app import create_app
from bootstrap import __version__


def test_health_is_ready_without_runtime_adapters() -> None:
    response = TestClient(create_app()).get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
    assert response.headers["X-Request-ID"]
