"""Unit tests for plugin/runtime semver compatibility."""

from __future__ import annotations

from application.services.version_compatibility import (
    COMPATIBLE_PLUGIN_RANGE,
    is_plugin_compatible,
    parse_semver,
)


def test_compatible_plugin_range_covers_current_minor() -> None:
    assert COMPATIBLE_PLUGIN_RANGE == ">=0.1.0,<0.2.0"
    assert is_plugin_compatible("0.1.0")
    assert is_plugin_compatible("0.1.9")
    assert not is_plugin_compatible("0.0.9")
    assert not is_plugin_compatible("0.2.0")
    assert not is_plugin_compatible("1.0.0")
    assert not is_plugin_compatible("not-a-version")
    assert parse_semver("0.1.0") == (0, 1, 0)
