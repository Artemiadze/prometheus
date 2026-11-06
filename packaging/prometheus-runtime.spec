# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onefile spec for prometheus-runtime.

Embedding model weights and HuggingFace/FastEmbed caches are intentionally
NOT bundled. They are downloaded into the runtime data_dir at first use.
"""

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

block_cipher = None

_ROOT = Path(SPECPATH).resolve().parent
_RUNTIME_SRC = _ROOT / "apps" / "prometheus-runtime" / "src"
_DIST_NAME = os.environ.get("PROMETHEUS_BINARY_NAME", "prometheus-runtime")

datas: list[tuple[str, str]] = []
binaries: list[tuple[str, str]] = []
hiddenimports: list[str] = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "pydantic.deprecated.decorator",
    "sqlite_vec",
    "fastembed",
    "onnxruntime",
    "tokenizers",
]

for package in ("onnxruntime", "tokenizers", "fastembed", "sqlite_vec"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

binaries += collect_dynamic_libs("onnxruntime")
binaries += collect_dynamic_libs("sqlite_vec")

a = Analysis(
    [str(_RUNTIME_SRC / "bootstrap" / "cli.py")],
    pathex=[str(_RUNTIME_SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "mypy",
        "black",
        "ruff",
        "importlinter",
        "IPython",
        "notebook",
        "tkinter",
        "qdrant_client",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=_DIST_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
