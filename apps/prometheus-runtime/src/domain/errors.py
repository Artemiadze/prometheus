"""Stable, presentation-safe error types shared by the runtime."""

from typing import ClassVar


class PrometheusError(Exception):
    """Base runtime error carrying a stable machine-readable code."""

    code: ClassVar[str] = "PROMETHEUS_ERROR"
    default_message: ClassVar[str] = "Prometheus runtime error"

    def __init__(self) -> None:
        super().__init__(self.default_message)


class InvariantViolationError(PrometheusError):
    """Raised when a domain entity would violate an invariant."""

    code = "INVARIANT_VIOLATION"
    default_message = "Domain invariant violated"


class InvalidIdentifierError(PrometheusError):
    """Raised when an identifier has an unsupported format."""

    code = "INVALID_IDENTIFIER"
    default_message = "Identifier format is invalid"


class InvalidPathError(PrometheusError):
    """Raised when a path is unsafe or not relative to a Vault."""

    code = "INVALID_PATH"
    default_message = "Path must be safe and relative to the Vault"


class InvalidSearchScopeError(PrometheusError):
    """Raised when search-scope parameters do not match its mode."""

    code = "INVALID_SEARCH_SCOPE"
    default_message = "Search scope parameters are invalid"


class ConfigurationError(PrometheusError):
    """Raised when runtime configuration is invalid."""

    code = "CONFIGURATION_INVALID"

    def __init__(self, message: str) -> None:
        Exception.__init__(self, message)


class AdapterNotConfiguredError(PrometheusError):
    """Raised when a not-yet-configured adapter is requested."""

    code = "ADAPTER_NOT_CONFIGURED"

    def __init__(self, message: str) -> None:
        Exception.__init__(self, message)
