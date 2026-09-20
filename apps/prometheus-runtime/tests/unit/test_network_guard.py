"""Tests for the loopback-only network guard."""

from __future__ import annotations

import socket
from collections.abc import Generator

import pytest

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


def test_uninstall_restores_original_socket_type() -> None:
    original_socket = socket.socket

    NetworkGuard.install()
    assert socket.socket is not original_socket

    NetworkGuard.uninstall()
    assert socket.socket is original_socket
