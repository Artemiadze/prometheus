"""Tests for session-token enforcement on protected HTTP routes."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.requests import Request

from adapters.inbound.http.app import create_app
from adapters.inbound.http.auth import UnauthorizedError, require_session_token
from adapters.outbound.filesystem.data_dir import ensure_layout
from adapters.outbound.filesystem.logging_setup import configure_logging
from bootstrap.config import RuntimeSettings
from fakes import FakeLanguageModel

_DEFAULT_TOKEN = SecretStr("test-token")


def _client(*, token: SecretStr | None = _DEFAULT_TOKEN) -> TestClient:
    return TestClient(
        create_app(SimpleNamespace(settings=RuntimeSettings(session_token=token))),
        base_url="http://127.0.0.1:8765",
    )


def test_health_remains_open_without_authorization() -> None:
    response = _client().get("/v1/health")

    assert response.status_code == 200
    assert "test-token" not in response.text


def test_missing_authorization_header_returns_401_envelope() -> None:
    response = _client().get("/v1/models")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert "test-token" not in response.text


def test_wrong_token_returns_401_envelope() -> None:
    response = _client().get(
        "/v1/models", headers={"Authorization": "Bearer wrong-token"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert "test-token" not in response.text
    assert "wrong-token" not in response.text


def test_non_bearer_scheme_returns_401() -> None:
    response = _client().get(
        "/v1/models", headers={"Authorization": "Basic test-token"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_raw_token_without_bearer_scheme_returns_401() -> None:
    response = _client().get("/v1/models", headers={"Authorization": "test-token"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_non_ascii_authorization_token_returns_401_not_500() -> None:
    app = SimpleNamespace(
        state=SimpleNamespace(
            container=SimpleNamespace(
                settings=RuntimeSettings(session_token=_DEFAULT_TOKEN)
            )
        )
    )
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/v1/models",
        "raw_path": b"/v1/models",
        "query_string": b"",
        "headers": [(b"authorization", "Bearer токен".encode())],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8765),
        "app": app,
    }

    with pytest.raises(UnauthorizedError):
        require_session_token(Request(scope))


def test_missing_configured_token_fails_closed() -> None:
    response = _client(token=None).get(
        "/v1/models", headers={"Authorization": "Bearer anything"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_valid_bearer_token_is_accepted_for_models_route() -> None:
    client = TestClient(
        create_app(
            SimpleNamespace(
                settings=RuntimeSettings(session_token=_DEFAULT_TOKEN),
                language_model=FakeLanguageModel(),
            )
        ),
        base_url="http://127.0.0.1:8765",
    )

    response = client.get(
        "/v1/models",
        headers={
            "Authorization": "Bearer test-token",
            "X-Prometheus-Plugin-Version": "0.1.0",
        },
    )

    assert response.status_code == 200
    assert "test-token" not in response.text


def test_failed_auth_does_not_write_token_to_runtime_log(tmp_path: Path) -> None:
    layout = ensure_layout(tmp_path / "data")
    configure_logging(layout)
    token = "session-token-must-never-appear"

    response = TestClient(
        create_app(
            SimpleNamespace(settings=RuntimeSettings(session_token=SecretStr(token)))
        ),
        base_url="http://127.0.0.1:8765",
    ).get("/v1/models", headers={"Authorization": f"Bearer {token}-wrong"})

    log_text = (
        (layout.logs / "runtime.log").read_text(encoding="utf-8")
        if (layout.logs / "runtime.log").exists()
        else "".join(
            path.read_text(encoding="utf-8")
            for path in layout.logs.glob("runtime.log*")
        )
    )

    assert response.status_code == 401
    assert token not in response.text
    assert token not in log_text
