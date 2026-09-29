"""Tests for the runtime command-line contract."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bootstrap import __version__
from bootstrap.cli import app

runner = CliRunner()


def test_version_exits_successfully() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_occupied_port_has_clear_nonzero_exit(tmp_path: Path) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]

        result = runner.invoke(
            app,
            [
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--data-dir",
                str(tmp_path),
                "--session-token",
                "test-token",
            ],
        )

    assert result.exit_code != 0
    assert "unavailable" in result.stderr


def test_serve_requires_session_token(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            "18765",
            "--data-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 2
    assert "session token is required" in result.stderr.casefold()
    assert "test-token" not in result.stdout
    assert "test-token" not in result.stderr


def test_network_guard_installs_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import uvicorn

    from adapters.outbound.network.guard import NetworkGuard
    from bootstrap import cli as cli_module

    installed: list[bool] = []

    class _FakeContainer:
        job_store = object()

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

    monkeypatch.setattr(NetworkGuard, "install", lambda: installed.append(True))
    monkeypatch.setattr(cli_module, "configure_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_module, "_assert_port_available", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_module, "Container", _FakeContainer)
    monkeypatch.setattr(cli_module, "VaultContainerRegistry", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli_module, "create_app", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(uvicorn, "run", lambda *_args, **_kwargs: None)

    result = runner.invoke(
        app,
        [
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            "18766",
            "--data-dir",
            str(tmp_path),
            "--session-token",
            "test-token",
        ],
    )

    assert result.exit_code == 0
    assert installed == [True]


def test_network_guard_skipped_when_embedding_download_allowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import uvicorn
    from pydantic import SecretStr

    from adapters.outbound.network.guard import NetworkGuard
    from bootstrap import cli as cli_module
    from bootstrap.config import RuntimeSettings

    installed: list[bool] = []

    class _FakeContainer:
        job_store = object()

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

    monkeypatch.setattr(
        cli_module,
        "load_settings",
        lambda *_args, **_kwargs: RuntimeSettings(
            data_dir=tmp_path,
            session_token=SecretStr("test-token"),
            embedding_allow_download=True,
            port=18767,
        ),
    )
    monkeypatch.setattr(NetworkGuard, "install", lambda: installed.append(True))
    monkeypatch.setattr(cli_module, "configure_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_module, "_assert_port_available", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli_module, "Container", _FakeContainer)
    monkeypatch.setattr(cli_module, "VaultContainerRegistry", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli_module, "create_app", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(uvicorn, "run", lambda *_args, **_kwargs: None)

    result = runner.invoke(
        app,
        [
            "serve",
            "--data-dir",
            str(tmp_path),
            "--session-token",
            "test-token",
        ],
    )

    assert result.exit_code == 0
    assert installed == []


def test_doctor_exits_nonzero_on_blocking_problems(tmp_path: Path) -> None:
    result = runner.invoke(app, ["doctor", "--data-dir", str(tmp_path)])

    assert result.exit_code == 1
    assert "[FAIL] embedding_model" in result.stdout
    assert "recommendation:" in result.stdout
    assert "Prometheus runtime doctor" in result.stdout


def test_doctor_does_not_mutate_data_dir(tmp_path: Path) -> None:
    result = runner.invoke(app, ["doctor", "--data-dir", str(tmp_path)])

    assert result.exit_code == 1
    assert list(tmp_path.iterdir()) == []
