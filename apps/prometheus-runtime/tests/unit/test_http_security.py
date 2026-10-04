"""Tests for browser and Host-header restrictions on the localhost API."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from httpx import Response
from pydantic import SecretStr

from adapters.inbound.http.app import create_app
from bootstrap.config import RuntimeSettings


def _header_names(response: Response) -> set[str]:
    return {key.casefold() for key in response.headers}


def _client(*, port: int = 8765) -> TestClient:
    return TestClient(
        create_app(
            SimpleNamespace(
                settings=RuntimeSettings(port=port, session_token=SecretStr("tok"))
            )
        ),
        base_url=f"http://127.0.0.1:{port}",
    )


def test_cross_origin_request_is_rejected_with_a_stable_error() -> None:
    response = _client().get("/v1/health", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CROSS_ORIGIN_FORBIDDEN"
    assert "access-control-allow-origin" not in _header_names(response)


def test_null_origin_is_rejected() -> None:
    response = _client().get("/v1/health", headers={"Origin": "null"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CROSS_ORIGIN_FORBIDDEN"


def test_obsidian_origin_is_allowed_and_receives_cors_headers() -> None:
    response = _client().get("/v1/health", headers={"Origin": "app://obsidian.md"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "app://obsidian.md"
    assert "X-Request-ID" in response.headers["access-control-expose-headers"]


def test_loopback_http_origin_is_allowed() -> None:
    response = _client().get("/v1/health", headers={"Origin": "http://127.0.0.1:1234"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:1234"


def test_preflight_from_obsidian_is_accepted() -> None:
    response = _client().options(
        "/v1/models",
        headers={
            "Origin": "app://obsidian.md",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-request-id",
        },
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "app://obsidian.md"
    assert "Authorization" in response.headers["access-control-allow-headers"]


def test_preflight_from_foreign_origin_has_no_cors_allow_headers() -> None:
    response = _client().options(
        "/v1/models",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CROSS_ORIGIN_FORBIDDEN"
    assert "access-control-allow-origin" not in _header_names(response)


def test_request_with_an_untrusted_host_is_rejected() -> None:
    response = _client().get("/v1/health", headers={"Host": "evil.example"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNTRUSTED_HOST"


def test_host_without_port_is_rejected() -> None:
    response = _client().get("/v1/health", headers={"Host": "127.0.0.1"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNTRUSTED_HOST"


def test_host_with_wrong_port_is_rejected() -> None:
    response = _client(port=8765).get("/v1/health", headers={"Host": "127.0.0.1:9999"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNTRUSTED_HOST"


def test_loopback_request_without_origin_is_allowed() -> None:
    response = _client().get("/v1/health")

    assert response.status_code == 200
