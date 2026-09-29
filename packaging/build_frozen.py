#!/usr/bin/env python3
"""Build a platform-named frozen prometheus-runtime binary with PyInstaller."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

RELEASE_TARGETS = frozenset({"linux-x64", "win-x64", "macos-x64", "macos-arm64"})

ARTIFACT_NAMES: dict[str, str] = {
    "linux-x64": "prometheus-runtime-linux-x64",
    "win-x64": "prometheus-runtime.exe",
    "macos-x64": "prometheus-runtime-macos-x64",
    "macos-arm64": "prometheus-runtime-macos-arm64",
}

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC = Path(__file__).resolve().parent / "prometheus-runtime.spec"
_PYPROJECT = _REPO_ROOT / "apps" / "prometheus-runtime" / "pyproject.toml"
_DIST_DIR = _REPO_ROOT / "packaging" / "dist"
_WORK_DIR = _REPO_ROOT / "packaging" / "build"


def read_package_version() -> str:
    text = _PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise RuntimeError(f"Could not read version from {_PYPROJECT}")
    return match.group(1)


def detect_release_target() -> str:
    system = platform.system().casefold()
    machine = platform.machine().casefold()
    if system == "windows":
        return "win-x64"
    if system == "darwin":
        return "macos-arm64" if machine in {"arm64", "aarch64"} else "macos-x64"
    if system == "linux":
        if machine in {"x86_64", "amd64"}:
            return "linux-x64"
        raise RuntimeError(f"Unsupported Linux architecture for release artifacts: {machine}")
    raise RuntimeError(f"Unsupported platform for release artifacts: {system}/{machine}")


def write_checksum(artifact: Path) -> Path:
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    checksum_path = Path(str(artifact) + ".sha256")
    checksum_path.write_text(f"{digest}  {artifact.name}\n", encoding="utf-8")
    return checksum_path


def build(*, target: str, skip_checksum: bool) -> Path:
    if target not in RELEASE_TARGETS:
        raise SystemExit(f"Unknown release target {target!r}; expected one of {sorted(RELEASE_TARGETS)}")

    version = read_package_version()
    artifact_name = ARTIFACT_NAMES[target]
    print(f"Building prometheus-runtime {version} for {target} -> {artifact_name}", flush=True)

    if _DIST_DIR.exists():
        shutil.rmtree(_DIST_DIR)
    if _WORK_DIR.exists():
        shutil.rmtree(_WORK_DIR)
    _DIST_DIR.mkdir(parents=True, exist_ok=True)
    _WORK_DIR.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PROMETHEUS_BINARY_NAME"] = artifact_name
    env["PROMETHEUS_RELEASE_TARGET"] = target

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        f"--distpath={_DIST_DIR}",
        f"--workpath={_WORK_DIR}",
        str(_SPEC),
    ]
    subprocess.run(cmd, check=True, cwd=_REPO_ROOT, env=env)

    artifact = _DIST_DIR / artifact_name
    if not artifact.exists():
        # PyInstaller on Windows may emit .exe even when name already ends with .exe
        candidates = list(_DIST_DIR.glob("prometheus-runtime*"))
        raise RuntimeError(f"Expected artifact {artifact}; found {candidates}")

    if os.name != "nt":
        artifact.chmod(artifact.stat().st_mode | 0o111)

    if not skip_checksum:
        checksum = write_checksum(artifact)
        print(f"Wrote {checksum}", flush=True)

    print(f"Artifact: {artifact}", flush=True)
    return artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        default=os.environ.get("PROMETHEUS_RELEASE_TARGET") or detect_release_target(),
        choices=sorted(RELEASE_TARGETS),
        help="Release target matching plugin runtimeRelease.ts names",
    )
    parser.add_argument(
        "--skip-checksum",
        action="store_true",
        help="Do not write the .sha256 sidecar (CI may write it separately)",
    )
    args = parser.parse_args(argv)
    build(target=args.target, skip_checksum=args.skip_checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
