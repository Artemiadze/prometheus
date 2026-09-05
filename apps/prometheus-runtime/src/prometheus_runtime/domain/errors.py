"""Domain and bootstrap-safe error types."""


class PrometheusRuntimeError(Exception):
    """Base error for failures with a safe presentation message."""


class ConfigurationError(PrometheusRuntimeError):
    """Raised when runtime configuration is invalid."""


class AdapterNotConfiguredError(PrometheusRuntimeError):
    """Raised when a not-yet-configured adapter is requested."""
