"""Tests for the minimal HTTP application."""

from fastapi.testclient import TestClient

from prometheus_runtime import __version__
from prometheus_runtime.adapters.inbound.http.app import create_app


def test_health_is_ready_without_runtime_adapters() -> None:
    response = TestClient(create_app()).get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
    assert response.headers["X-Request-ID"]
