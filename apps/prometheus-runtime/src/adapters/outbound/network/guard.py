"""Process-wide guard that permits outbound connections only to loopback."""

from __future__ import annotations

import ipaddress
import socket
from types import TracebackType
from typing import Any

from domain.errors import ConfigurationError


def _is_loopback_destination(address: object) -> bool:
    """Return whether a socket address is local without performing DNS lookups."""

    if isinstance(address, str):
        return True  # Unix-domain socket paths are local IPC.
    if not isinstance(address, tuple) or not address or not isinstance(address[0], str):
        return False
    host = address[0]
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


_ORIGINAL_SOCKET = socket.socket


class _GuardedSocket(_ORIGINAL_SOCKET):
    def connect(self, address: Any) -> None:
        _assert_loopback(address)
        super().connect(address)

    def connect_ex(self, address: Any) -> int:
        _assert_loopback(address)
        return int(super().connect_ex(address))


class NetworkGuard:
    """Block non-loopback outbound socket connections while installed."""

    _original_socket: type[socket.socket] | None = None

    @classmethod
    def install(cls) -> None:
        """Install the guard once for the current Python process."""

        if cls._original_socket is not None:
            return
        cls._original_socket = socket.socket
        socket.socket = _GuardedSocket  # type: ignore[misc]

    @classmethod
    def uninstall(cls) -> None:
        """Restore the original socket implementation after a scoped use."""

        if cls._original_socket is None:
            return
        socket.socket = cls._original_socket  # type: ignore[misc]
        cls._original_socket = None

    def __enter__(self) -> NetworkGuard:
        self.install()
        return self

    def __exit__(
        self,
        _: type[BaseException] | None,
        __: BaseException | None,
        ___: TracebackType | None,
    ) -> None:
        self.uninstall()


def _assert_loopback(address: object) -> None:
    if not _is_loopback_destination(address):
        raise ConfigurationError("Outgoing network connections must target localhost")
