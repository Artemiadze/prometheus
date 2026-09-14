"""Local Ollama outbound adapter."""

from adapters.outbound.ollama.adapter import OllamaLanguageModel
from adapters.outbound.ollama.errors import (
    LlmContextExceededError,
    LlmModelNotFoundError,
    LlmTimeoutError,
    OllamaUnavailableError,
)

__all__ = [
    "LlmContextExceededError",
    "LlmModelNotFoundError",
    "LlmTimeoutError",
    "OllamaLanguageModel",
    "OllamaUnavailableError",
]
