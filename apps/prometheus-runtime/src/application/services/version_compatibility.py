"""Plugin ↔ runtime version compatibility policy."""

from __future__ import annotations

from re import fullmatch

# Inclusive lower bound and exclusive upper bound for the plugin semver.
MIN_PLUGIN_VERSION = (0, 1, 0)
MAX_PLUGIN_VERSION_EXCLUSIVE = (0, 2, 0)
COMPATIBLE_PLUGIN_RANGE = ">=0.1.0,<0.2.0"

#: Stable localhost HTTP API contract version, independent of the package release.
API_VERSION = "0.1.0"

_SEMVER_PATTERN = r"([0-9]+)\.([0-9]+)\.([0-9]+)"


def parse_semver(value: str) -> tuple[int, int, int] | None:
    """Parse a strict MAJOR.MINOR.PATCH version string.

    Prerelease and build metadata (``-rc.1``, ``+meta``) are rejected so that
    negotiation stays deterministic between plugin and runtime.
    """

    match = fullmatch(_SEMVER_PATTERN, value.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def is_plugin_compatible(version: str) -> bool:
    """Return whether a plugin version is accepted by this runtime."""

    parsed = parse_semver(version)
    if parsed is None:
        return False
    return MIN_PLUGIN_VERSION <= parsed < MAX_PLUGIN_VERSION_EXCLUSIVE
