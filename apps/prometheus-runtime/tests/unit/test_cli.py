"""Tests for the runtime command-line contract."""

from __future__ import annotations

import socket
from pathlib import Path

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
