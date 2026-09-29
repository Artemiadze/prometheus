"""Tests for the loopback-only network guard."""

from __future__ import annotations

import json
import socket
from collections.abc import Generator
from pathlib import Path

import pytest

from adapters.outbound.filesystem.data_dir import ensure_layout
from adapters.outbound.filesystem.logging_setup import configure_logging
from adapters.outbound.network.guard import NetworkGuard
from domain.errors import ConfigurationError


@pytest.fixture(autouse=True)
def reset_network_guard() -> Generator[None]:
    NetworkGuard.uninstall()
    yield
    NetworkGuard.uninstall()


def test_loopback_connection_is_allowed() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]

        with NetworkGuard(), socket.create_connection(("127.0.0.1", port)) as client:
            peer, _ = listener.accept()
            peer.close()
            assert client.getpeername()[0] == "127.0.0.1"


def test_external_connect_and_connect_ex_raise_configuration_error() -> None:
    with NetworkGuard(), socket.socket() as client:
        with pytest.raises(ConfigurationError, match="target localhost"):
            client.connect(("8.8.8.8", 53))
        with pytest.raises(ConfigurationError, match="target localhost"):
            client.connect_ex(("example.com", 80))


def test_external_dns_lookup_is_blocked() -> None:
    with NetworkGuard(), pytest.raises(ConfigurationError, match="target localhost"):
        socket.getaddrinfo("example.com", 80)


def test_localhost_dns_lookup_remains_allowed() -> None:
    with NetworkGuard():
        results = socket.getaddrinfo("localhost", 80, type=socket.SOCK_STREAM)

    assert results


def test_udp_sendto_external_address_is_blocked() -> None:
    with (
        NetworkGuard(),
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client,
        pytest.raises(ConfigurationError, match="target localhost"),
    ):
        client.sendto(b"ping", ("8.8.8.8", 53))


def test_blocked_attempt_is_recorded_in_privacy_safe_log(tmp_path: Path) -> None:
    layout = ensure_layout(tmp_path / "data")
    configure_logging(layout)

    with (
        NetworkGuard(),
        socket.socket() as client,
        pytest.raises(ConfigurationError, match="target localhost"),
    ):
        client.connect(("8.8.8.8", 53))

    record = json.loads((layout.logs / "runtime.log").read_text(encoding="utf-8"))
    assert record["event"] == "network.blocked"
    assert "8.8.8.8" not in (layout.logs / "runtime.log").read_text(encoding="utf-8")


def test_uninstall_restores_original_socket_type() -> None:
    original_socket = socket.socket
    original_getaddrinfo = socket.getaddrinfo

    NetworkGuard.install()
    assert socket.socket is not original_socket
    assert socket.getaddrinfo is not original_getaddrinfo

    NetworkGuard.uninstall()
    assert socket.socket is original_socket
    assert socket.getaddrinfo is original_getaddrinfo
