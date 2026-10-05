"""Tests for immutable runtime settings and source precedence."""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from bootstrap.config import RuntimeSettings, load_settings
from domain.errors import ConfigurationError


@pytest.fixture(autouse=True)
def clean_prometheus_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in os.environ:
        if name.startswith("PROMETHEUS_"):
            monkeypatch.delenv(name)


def test_defaults_match_product_settings() -> None:
    settings = load_settings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 8765
    assert settings.embedding_batch_size == 64
    assert settings.embedding_threads is None
    assert not settings.embedding_allow_download
    assert settings.chunk_size == 700
    assert settings.chunk_overlap == 80
    assert settings.top_k == 10
    assert settings.retrieval_mode == "dense"
    assert settings.hybrid_rrf_k == 60
    assert settings.hybrid_dense_weight == 1.0
    assert settings.hybrid_lexical_weight == 1.0
    assert settings.hybrid_candidate_multiplier == 2
    assert not settings.reranker_enabled
    assert settings.reranker_model == "Xenova/ms-marco-MiniLM-L-6-v2"
    assert settings.reranker_batch_size == 32
    assert settings.reranker_candidate_limit == 20
    assert not settings.reranker_allow_download
    assert settings.llm_host == "http://127.0.0.1:11434"
    assert settings.llm_model == "qwen3:4b"
    assert settings.llm_temperature == 0.1
    assert settings.llm_context_size == 12288
    assert settings.llm_output_reserve == 4096
    assert settings.llm_timeout_seconds == 600


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMETHEUS_PORT", "9000")
    monkeypatch.setenv("PROMETHEUS_LOG_LEVEL", "debug")

    settings = load_settings()

    assert settings.port == 9000
    assert settings.log_level == "DEBUG"


def test_environment_overrides_retrieval_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMETHEUS_RETRIEVAL_MODE", "hybrid")

    assert load_settings().retrieval_mode == "hybrid"


def test_cli_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMETHEUS_PORT", "9000")

    assert load_settings({"port": 9100}).port == 9100


def test_invalid_chunk_overlap_has_safe_startup_error() -> None:
    with pytest.raises(ConfigurationError, match="chunk_overlap must be smaller"):
        load_settings({"chunk_size": 100, "chunk_overlap": 100})


def test_invalid_llm_output_reserve_has_safe_startup_error() -> None:
    with pytest.raises(ConfigurationError, match="llm_output_reserve must be smaller"):
        load_settings({"llm_context_size": 1024, "llm_output_reserve": 1024})


def test_non_loopback_host_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="loopback"):
        load_settings({"host": "0.0.0.0"})


@pytest.mark.parametrize(
    "llm_host",
    [
        "https://api.example.com",
        "http://192.168.1.20:11434",
        "file:///tmp/ollama",
        "http://user:password@localhost:11434",
    ],
)
def test_non_local_llm_host_is_rejected(llm_host: str) -> None:
    with pytest.raises(
        ConfigurationError, match="llm_host must be an HTTP loopback URL"
    ):
        load_settings({"llm_host": llm_host})


@pytest.mark.parametrize(
    "llm_host",
    ["http://localhost:11434", "http://127.0.0.1:11434/api", "http://[::1]:11434"],
)
def test_local_ollama_urls_are_accepted(llm_host: str) -> None:
    assert load_settings({"llm_host": llm_host}).llm_host == llm_host


@pytest.mark.parametrize(
    "overrides",
    [
        {"embedding_batch_size": 0},
        {"embedding_threads": 0},
    ],
)
def test_invalid_embedding_limits_have_safe_startup_error(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ConfigurationError):
        load_settings(overrides)


def test_non_fastembed_provider_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="embedding_provider"):
        load_settings({"embedding_provider": "openai"})


def test_settings_are_immutable() -> None:
    settings = RuntimeSettings()

    with pytest.raises(ValidationError, match="frozen"):
        settings.port = 9000


def test_error_does_not_expose_session_token() -> None:
    secret = "do-not-print-this-token"

    with pytest.raises(ConfigurationError) as caught:
        load_settings({"session_token": secret, "port": 1})

    assert secret not in str(caught.value)
