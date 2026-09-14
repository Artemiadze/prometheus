"""Provider-independent language-model metadata and generation results."""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import InvariantViolationError


@dataclass(frozen=True, slots=True)
class LocalLlmModel:
    """One language model installed in the configured local runtime."""

    name: str
    size_bytes: int
    quantization: str | None = None

    def __post_init__(self) -> None:
        name = self.name.strip()
        quantization = self.quantization.strip() if self.quantization is not None else None
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "quantization", quantization or None)
        if not name or self.size_bytes < 0:
            raise InvariantViolationError()


@dataclass(frozen=True, slots=True)
class LlmGeneration:
    """Safe subset of an LLM response used by application use cases."""

    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    done_reason: str | None = None

    def __post_init__(self) -> None:
        text = self.text.strip()
        model = self.model.strip()
        done_reason = self.done_reason.strip() if self.done_reason is not None else None
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "done_reason", done_reason or None)
        if (
            not text
            or not model
            or (self.prompt_tokens is not None and self.prompt_tokens < 0)
            or (self.completion_tokens is not None and self.completion_tokens < 0)
        ):
            raise InvariantViolationError()
