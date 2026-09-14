"""Stable, privacy-safe failures exposed by the local Ollama adapter."""

from domain.errors import PrometheusError


class OllamaUnavailableError(PrometheusError):
    """Raised when the configured local Ollama runtime cannot be reached."""

    code = "OLLAMA_UNAVAILABLE"
    default_message = "Local Ollama runtime is unavailable"


class LlmModelNotFoundError(PrometheusError):
    """Raised when the selected model is not installed in local Ollama."""

    code = "LLM_MODEL_NOT_FOUND"
    default_message = "Selected local language model is not installed"


class LlmTimeoutError(PrometheusError):
    """Raised when local model generation exceeds its configured timeout."""

    code = "LLM_TIMEOUT"
    default_message = "Local language model request timed out"


class LlmContextExceededError(PrometheusError):
    """Raised when Ollama rejects a prompt that exceeds the model context."""

    code = "LLM_CONTEXT_EXCEEDED"
    default_message = "Language model context size was exceeded"
