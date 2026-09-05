"""Resolve and create runtime-owned data directories."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DataDirLayout:
    """Paths owned by the runtime, all located outside an Obsidian Vault."""

    root: Path
    models: Path
    embeddings: Path
    vaults: Path
    state: Path
    logs: Path


def resolve_data_dir(explicit: Path | None = None) -> Path:
    """Return an explicit data directory or the native per-user default."""

    if explicit is not None:
        return explicit.expanduser().resolve()

    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "Prometheus"
    elif sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise RuntimeError("LOCALAPPDATA is required to resolve the Windows data directory")
        root = Path(local_app_data) / "Prometheus"
    else:
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        root = (
            Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
        ) / "prometheus"
    return root.expanduser().resolve()


def _create_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if sys.platform != "win32":
        path.chmod(0o700)


def ensure_layout(data_dir: Path) -> DataDirLayout:
    """Create the runtime directory layout with user-only permissions."""

    root = data_dir.expanduser().resolve()
    models = root / "models"
    embeddings = models / "embeddings"
    vaults = root / "vaults"
    state = root / "state"
    logs = root / "logs"
    for path in (root, models, embeddings, vaults, state, logs):
        _create_private_directory(path)
    return DataDirLayout(
        root=root,
        models=models,
        embeddings=embeddings,
        vaults=vaults,
        state=state,
        logs=logs,
    )


def vault_dir(layout: DataDirLayout, vault_id: str) -> Path:
    """Create and return a private runtime directory for one validated Vault ID."""

    if not vault_id or vault_id in {".", ".."} or Path(vault_id).name != vault_id:
        raise ValueError("vault_id must be a non-empty path segment")
    path = layout.vaults / vault_id
    _create_private_directory(path)
    return path
