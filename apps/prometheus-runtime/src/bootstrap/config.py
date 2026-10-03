"""Validated, immutable runtime configuration."""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.errors import ConfigurationError

LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
RetrievalMode = Literal["dense", "hybrid"]


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
    embedding_provider: Literal["fastembed"] = "fastembed"
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_batch_size: int = Field(default=64, gt=0)
    embedding_threads: int | None = Field(default=None, gt=0)
    embedding_allow_download: bool = False
    chunk_size: int = Field(default=700, gt=0)
    chunk_overlap: int = Field(default=80, ge=0)
    job_progress_interval: int = Field(default=10, gt=0)
    shutdown_grace_seconds: float = Field(default=10.0, gt=0)
    max_document_chars: int = Field(default=2_000_000, gt=0)
    max_chunks_per_document: int = Field(default=10_000, gt=0)
    top_k: int = Field(default=10, gt=0)
    retrieval_mode: RetrievalMode = "dense"
    hybrid_rrf_k: int = Field(default=60, gt=0)
    hybrid_dense_weight: float = Field(default=1.0, gt=0.0)
    hybrid_lexical_weight: float = Field(default=1.0, gt=0.0)
    hybrid_candidate_multiplier: int = Field(default=2, ge=1)
    reranker_enabled: bool = False
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    reranker_batch_size: int = Field(default=32, gt=0)
    reranker_candidate_limit: int = Field(default=20, gt=0)
    reranker_allow_download: bool = False
    llm_host: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3:4b"
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_context_size: int = Field(default=8192, gt=0)
    llm_output_reserve: int = Field(default=1024, gt=0)
    llm_timeout_seconds: float = Field(default=120.0, gt=0)
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

    @field_validator("llm_host")
    @classmethod
    def validate_llm_host(cls, value: str) -> str:
        """Allow Ollama only over an uncredentialed HTTP loopback URL."""

        parsed = urlsplit(value.strip())
        if (
            parsed.scheme != "http"
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") not in {"", "/api"}
        ):
            raise ValueError("llm_host must be an HTTP loopback URL")
        try:
            is_loopback = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            is_loopback = parsed.hostname.casefold() == "localhost"
        if not is_loopback:
            raise ValueError("llm_host must be an HTTP loopback URL")
        return value.strip()

    @model_validator(mode="after")
    def validate_chunking(self) -> RuntimeSettings:
        """Validate paired chunking and LLM budget settings."""

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if self.llm_output_reserve >= self.llm_context_size:
            raise ValueError("llm_output_reserve must be smaller than llm_context_size")
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
