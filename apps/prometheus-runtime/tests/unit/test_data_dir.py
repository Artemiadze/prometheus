"""Tests for platform data-directory resolution."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from prometheus_runtime.adapters.outbound.filesystem.data_dir import (
    ensure_layout,
    resolve_data_dir,
    vault_dir,
)


def test_explicit_path_has_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert resolve_data_dir(tmp_path / "custom") == (tmp_path / "custom").resolve()


@pytest.mark.parametrize(
    ("platform", "expected_suffix"),
    [
        ("linux", Path(".local/share/prometheus")),
        ("darwin", Path("Library/Application Support/Prometheus")),
    ],
)
def test_unix_platform_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    expected_suffix: Path,
) -> None:
    monkeypatch.setattr("sys.platform", platform)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    assert resolve_data_dir() == (tmp_path / expected_suffix).resolve()


def test_windows_platform_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert resolve_data_dir() == (tmp_path / "Prometheus").resolve()


def test_layout_is_private_and_outside_unrelated_vault(tmp_path: Path) -> None:
    source_vault = tmp_path / "Notes"
    source_vault.mkdir()
    layout = ensure_layout(tmp_path / "runtime-data")

    for path in (
        layout.root,
        layout.models,
        layout.embeddings,
        layout.vaults,
        layout.state,
        layout.logs,
    ):
        assert path.is_dir()
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
        assert source_vault not in path.parents


def test_vault_dir_rejects_path_traversal(tmp_path: Path) -> None:
    layout = ensure_layout(tmp_path / "runtime-data")

    with pytest.raises(ValueError, match="path segment"):
        vault_dir(layout, "../Notes")
