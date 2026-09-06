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
    assert settings.chunk_size == 700
    assert settings.chunk_overlap == 80
    assert settings.top_k == 10
    assert settings.llm_temperature == 0.1


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMETHEUS_PORT", "9000")
    monkeypatch.setenv("PROMETHEUS_LOG_LEVEL", "debug")

    settings = load_settings()

    assert settings.port == 9000
    assert settings.log_level == "DEBUG"


def test_cli_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMETHEUS_PORT", "9000")

    assert load_settings({"port": 9100}).port == 9100


def test_invalid_chunk_overlap_has_safe_startup_error() -> None:
    with pytest.raises(ConfigurationError, match="chunk_overlap must be smaller"):
        load_settings({"chunk_size": 100, "chunk_overlap": 100})


def test_non_loopback_host_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="loopback"):
        load_settings({"host": "0.0.0.0"})


def test_settings_are_immutable() -> None:
    settings = RuntimeSettings()

    with pytest.raises(ValidationError, match="frozen"):
        settings.port = 9000


def test_error_does_not_expose_session_token() -> None:
    secret = "do-not-print-this-token"

    with pytest.raises(ConfigurationError) as caught:
        load_settings({"session_token": secret, "port": 1})

    assert secret not in str(caught.value)
