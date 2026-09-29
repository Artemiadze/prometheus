"""Unit tests for plugin/runtime semver compatibility."""

from __future__ import annotations

from application.services.version_compatibility import (
    API_VERSION,
    COMPATIBLE_PLUGIN_RANGE,
    is_plugin_compatible,
    parse_semver,
)


def test_compatible_plugin_range_covers_current_minor() -> None:
    assert COMPATIBLE_PLUGIN_RANGE == ">=0.1.0,<0.2.0"
    assert API_VERSION == "0.1.0"
    assert is_plugin_compatible("0.1.0")
    assert is_plugin_compatible("0.1.9")
    assert not is_plugin_compatible("0.0.9")
    assert not is_plugin_compatible("0.2.0")
    assert not is_plugin_compatible("1.0.0")
    assert not is_plugin_compatible("not-a-version")
    assert parse_semver("0.1.0") == (0, 1, 0)


def test_boundary_versions_are_exclusive_at_upper_bound() -> None:
    assert is_plugin_compatible("0.1.0")
    assert is_plugin_compatible("0.1.99")
    assert not is_plugin_compatible("0.2.0")
    assert not is_plugin_compatible("0.0.0")


def test_prerelease_and_build_metadata_are_rejected() -> None:
    assert parse_semver("0.1.0-rc.1") is None
    assert parse_semver("0.1.0+build") is None
    assert parse_semver("v0.1.0") is None
    assert not is_plugin_compatible("0.1.0-alpha")
    assert not is_plugin_compatible("0.1.0+meta")
