"""Process-wide guard that permits outbound connections only to loopback."""

from __future__ import annotations

import ipaddress
import logging
import socket
from types import TracebackType
from typing import Any

from domain.errors import ConfigurationError

logger = logging.getLogger("prometheus_runtime")

_ORIGINAL_SOCKET = socket.socket
_ORIGINAL_GETADDRINFO = socket.getaddrinfo


def _is_loopback_host(host: str) -> bool:
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_loopback_destination(address: object) -> bool:
    """Return whether a socket address is local without performing DNS lookups."""

    if isinstance(address, str):
        return True  # Unix-domain socket paths are local IPC.
    if not isinstance(address, tuple) or not address or not isinstance(address[0], str):
        return False
    return _is_loopback_host(address[0])


def _record_blocked(kind: str) -> None:
    logger.warning("ignored", extra={"event": "network.blocked", "result_count": 1})
    _ = kind  # retained for call-site clarity without logging host/URL details


def _assert_loopback(address: object) -> None:
    if not _is_loopback_destination(address):
        _record_blocked("connect")
        raise ConfigurationError("Outgoing network connections must target localhost")


class _GuardedSocket(_ORIGINAL_SOCKET):
    def connect(self, address: Any) -> None:
        _assert_loopback(address)
        super().connect(address)

    def connect_ex(self, address: Any) -> int:
        _assert_loopback(address)
        return int(super().connect_ex(address))

    def sendto(self, data: Any, *args: Any) -> int:
        address = args[-1] if args else None
        if address is not None:
            _assert_loopback(address)
        return int(super().sendto(data, *args))

    def sendmsg(self, buffers: Any, *args: Any) -> int:
        if len(args) >= 3:
            _assert_loopback(args[2])
        return int(super().sendmsg(buffers, *args))


def _guarded_getaddrinfo(
    host: bytes | str | None,
    port: bytes | str | int | None,
    family: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0,
) -> list[tuple[Any, ...]]:
    if host not in {None, "", b""}:
        host_text = host.decode() if isinstance(host, bytes) else str(host)
        if not _is_loopback_host(host_text):
            _record_blocked("dns")
            raise ConfigurationError("Outgoing network connections must target localhost")
    return list(_ORIGINAL_GETADDRINFO(host, port, family, type, proto, flags))


class NetworkGuard:
    """Block non-loopback outbound socket connections while installed."""

    _original_socket: type[socket.socket] | None = None
    _original_getaddrinfo: Any | None = None

    @classmethod
    def install(cls) -> None:
        """Install the guard once for the current Python process."""

        if cls._original_socket is not None:
            return
        cls._original_socket = socket.socket
        cls._original_getaddrinfo = socket.getaddrinfo
        socket.socket = _GuardedSocket  # type: ignore[misc]
        socket.getaddrinfo = _guarded_getaddrinfo

    @classmethod
    def uninstall(cls) -> None:
        """Restore the original socket implementation after a scoped use."""

        if cls._original_socket is None:
            return
        socket.socket = cls._original_socket  # type: ignore[misc]
        if cls._original_getaddrinfo is not None:
            socket.getaddrinfo = cls._original_getaddrinfo
        cls._original_socket = None
        cls._original_getaddrinfo = None

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
