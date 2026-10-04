"""Tests for stable and privacy-safe runtime errors."""

from __future__ import annotations

import pytest

from domain.errors import (
    AdapterNotConfiguredError,
    ConfigurationError,
    InvalidIdentifierError,
    InvalidPathError,
    InvalidSearchScopeError,
    InvariantViolationError,
    PrometheusError,
)

pytestmark = pytest.mark.domain


def _all_error_types(root: type[PrometheusError]) -> set[type[PrometheusError]]:
    direct = set(root.__subclasses__())
    return direct | {nested for child in direct for nested in _all_error_types(child)}


def test_error_codes_are_present_and_unique() -> None:
    error_types: set[type[PrometheusError]] = {
        PrometheusError,
        *_all_error_types(PrometheusError),
    }
    codes = [error_type.code for error_type in error_types]

    assert all(codes)
    assert len(codes) == len(set(codes))


def test_domain_errors_have_fixed_messages_without_user_content() -> None:
    private_note = "private contents of the user's note"
    errors = (
        InvariantViolationError(),
        InvalidIdentifierError(),
        InvalidPathError(),
        InvalidSearchScopeError(),
    )

    assert all(private_note not in str(error) for error in errors)


def test_existing_bootstrap_errors_keep_safe_messages() -> None:
    assert str(ConfigurationError("Invalid port")) == "Invalid port"
    assert (
        str(AdapterNotConfiguredError("Embedder unavailable")) == "Embedder unavailable"
    )
