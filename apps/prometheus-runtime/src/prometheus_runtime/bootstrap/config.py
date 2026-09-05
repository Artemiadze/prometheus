"""Validated, immutable runtime configuration."""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from prometheus_runtime.domain.errors import ConfigurationError

LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]


class RuntimeSettings(BaseSettings):
    """Configuration loaded with CLI overrides taking precedence over environment."""

    model_config = SettingsConfigDict(
        env_prefix="PROMETHEUS_",
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1024, le=65535)
    data_dir: Path | None = None
    session_token: SecretStr | None = None
    embedding_provider: str = "fastembed"
    embedding_model: str = "intfloat/multilingual-e5-large"
    chunk_size: int = Field(default=700, gt=0)
    chunk_overlap: int = Field(default=80, ge=0)
    top_k: int = Field(default=10, gt=0)
    llm_host: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3:4b"
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    log_level: LogLevel = "INFO"

    @field_validator("host")
    @classmethod
    def validate_loopback_host(cls, value: str) -> str:
        """Reject interfaces that expose the runtime to the local network."""

        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("host must be a loopback IP address") from exc
        if not address.is_loopback:
            raise ValueError("host must be a loopback IP address")
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        """Accept case-insensitive textual log levels."""

        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_chunking(self) -> RuntimeSettings:
        """Require overlap to be smaller than the target chunk size."""

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


def _format_validation_error(error: ValidationError) -> str:
    problems: list[str] = []
    for item in error.errors(include_url=False, include_input=False):
        location = ".".join(str(part) for part in item["loc"]) or "settings"
        problems.append(f"{location}: {item['msg']}")
    return "Invalid runtime configuration: " + "; ".join(problems)


def load_settings(cli_overrides: Mapping[str, object] | None = None) -> RuntimeSettings:
    """Load defaults and environment, then apply non-None CLI values."""

    overrides: dict[str, Any] = {
        key: value for key, value in (cli_overrides or {}).items() if value is not None
    }
    try:
        return RuntimeSettings(**overrides)
    except ValidationError as exc:
        raise ConfigurationError(_format_validation_error(exc)) from exc
