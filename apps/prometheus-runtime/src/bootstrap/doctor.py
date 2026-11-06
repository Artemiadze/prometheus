"""Read-only environment diagnostics for `prometheus-runtime doctor`."""

from __future__ import annotations

import os
import platform
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import httpx

from adapters.outbound.filesystem.data_dir import resolve_data_dir
from bootstrap.config import RuntimeSettings

MEMORY_WARN_BYTES = 2 * 1024 * 1024 * 1024


class CheckStatus(StrEnum):
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    status: CheckStatus
    message: str
    recommendation: str


def format_doctor_report(checks: Sequence[DoctorCheck]) -> str:
    lines = ["Prometheus runtime doctor", ""]
    for check in checks:
        lines.append(f"[{check.status.value}] {check.name}")
        lines.append(f"  {check.message}")
        if check.recommendation:
            lines.append(f"  recommendation: {check.recommendation}")
        lines.append("")
    failures = sum(1 for check in checks if check.status is CheckStatus.FAIL)
    warnings = sum(1 for check in checks if check.status is CheckStatus.WARN)
    lines.append(f"Summary: {failures} failing, {warnings} warning(s)")
    return "\n".join(lines).rstrip() + "\n"


def doctor_exit_code(checks: Sequence[DoctorCheck]) -> int:
    return 1 if any(check.status is CheckStatus.FAIL for check in checks) else 0


def run_doctor(settings: RuntimeSettings) -> list[DoctorCheck]:
    """Execute all diagnostics without creating directories or mutating data."""

    data_dir = resolve_data_dir(settings.data_dir)
    return [
        check_data_dir(data_dir),
        check_ollama(settings.llm_host, settings.llm_model),
        check_embedding_model(
            data_dir,
            settings.embedding_model,
            allow_download=settings.embedding_allow_download,
        ),
        check_index(data_dir),
        check_memory(),
    ]


def check_data_dir(data_dir: Path) -> DoctorCheck:
    if not data_dir.exists():
        return DoctorCheck(
            name="data_dir",
            status=CheckStatus.WARN,
            message=f"{data_dir} does not exist yet",
            recommendation=(
                "Run `prometheus-runtime serve` once to create the layout, or mkdir the path."
            ),
        )
    if not data_dir.is_dir():
        return DoctorCheck(
            name="data_dir",
            status=CheckStatus.FAIL,
            message=f"{data_dir} exists but is not a directory",
            recommendation="Remove the conflicting path or choose another --data-dir.",
        )
    if not os.access(data_dir, os.R_OK | os.W_OK | os.X_OK):
        return DoctorCheck(
            name="data_dir",
            status=CheckStatus.FAIL,
            message=f"{data_dir} is not readable/writable",
            recommendation="Fix directory permissions for the current user.",
        )
    for relative in ("models", "models/embeddings", "vaults", "state", "logs"):
        path = data_dir / relative
        if path.exists() and not os.access(path, os.R_OK | os.W_OK | os.X_OK):
            return DoctorCheck(
                name="data_dir",
                status=CheckStatus.FAIL,
                message=f"{path} exists but is not readable/writable",
                recommendation="Fix subdirectory permissions for the current user.",
            )
    return DoctorCheck(
        name="data_dir",
        status=CheckStatus.OK,
        message=f"{data_dir} is present and writable",
        recommendation="",
    )


def check_ollama(
    llm_host: str,
    llm_model: str,
    *,
    client_factory: Callable[[], httpx.Client] | None = None,
) -> DoctorCheck:
    factory = client_factory or (lambda: httpx.Client(timeout=2.0))
    try:
        with factory() as client:
            response = client.get(f"{llm_host.rstrip('/')}/api/tags")
            response.raise_for_status()
            payload = response.json()
    except Exception as error:
        return DoctorCheck(
            name="ollama",
            status=CheckStatus.WARN,
            message=f"Ollama at {llm_host} is unreachable ({error})",
            recommendation="Install and start Ollama on loopback, then pull the configured model.",
        )

    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return DoctorCheck(
            name="ollama",
            status=CheckStatus.WARN,
            message="Ollama responded but the model list was not understood",
            recommendation="Upgrade Ollama or verify /api/tags returns a models array.",
        )
    names = {
        str(item.get("name", "")) for item in models if isinstance(item, dict) and item.get("name")
    }
    if llm_model not in names and not any(
        name == llm_model or name.startswith(f"{llm_model}:") for name in names
    ):
        return DoctorCheck(
            name="ollama",
            status=CheckStatus.WARN,
            message=f"Ollama is up but model {llm_model!r} was not found",
            recommendation=f"Run `ollama pull {llm_model}` or change PROMETHEUS_LLM_MODEL.",
        )
    return DoctorCheck(
        name="ollama",
        status=CheckStatus.OK,
        message=f"Ollama reachable; model {llm_model!r} is available",
        recommendation="",
    )


def check_embedding_model(
    data_dir: Path,
    model_id: str,
    *,
    allow_download: bool,
) -> DoctorCheck:
    cache_dir = data_dir / "models" / "embeddings"
    if _embedding_cache_looks_present(cache_dir, model_id):
        return DoctorCheck(
            name="embedding_model",
            status=CheckStatus.OK,
            message=f"Local embedding artifacts for {model_id!r} found under {cache_dir}",
            recommendation="",
        )

    if allow_download:
        return DoctorCheck(
            name="embedding_model",
            status=CheckStatus.WARN,
            message=f"Embedding model {model_id!r} is not cached yet",
            recommendation=(
                "First serve with PROMETHEUS_EMBEDDING_ALLOW_DOWNLOAD=true "
                "to download into data_dir."
            ),
        )
    return DoctorCheck(
        name="embedding_model",
        status=CheckStatus.FAIL,
        message=f"Embedding model {model_id!r} is missing under {cache_dir}",
        recommendation=(
            "Download once with PROMETHEUS_EMBEDDING_ALLOW_DOWNLOAD=true, then restart offline."
        ),
    )


def _embedding_cache_looks_present(cache_dir: Path, model_id: str) -> bool:
    if not cache_dir.is_dir():
        return False
    needle = model_id.replace("/", "--").casefold()
    alt = model_id.replace("/", "_").casefold()
    for path in cache_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(needle in part.casefold() or alt in part.casefold() for part in path.parts):
            return True
    return False


def check_index(data_dir: Path) -> DoctorCheck:
    vaults_root = data_dir / "vaults"
    if not vaults_root.is_dir():
        return DoctorCheck(
            name="index",
            status=CheckStatus.WARN,
            message="No vaults directory yet (not indexed)",
            recommendation="Open a Vault from the plugin and run a full sync/index.",
        )

    vault_dirs = [path for path in vaults_root.iterdir() if path.is_dir()]
    if not vault_dirs:
        return DoctorCheck(
            name="index",
            status=CheckStatus.WARN,
            message="Vaults directory is empty (not indexed)",
            recommendation="Open a Vault from the plugin and run a full sync/index.",
        )

    problems: list[str] = []
    warnings: list[str] = []
    ready = 0
    for vault_dir in sorted(vault_dirs):
        sqlite_path = vault_dir / "metadata.sqlite"
        legacy_qdrant = vault_dir / "qdrant"
        legacy_meta = vault_dir / "qdrant_metadata.json"
        if legacy_qdrant.exists() or legacy_meta.exists():
            warnings.append(f"{vault_dir.name}: legacy Qdrant files present (delete and reindex)")
        if not sqlite_path.is_file():
            continue
        try:
            import sqlite3

            from adapters.outbound.sqlite.connection import load_sqlite_vec

            connection = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
            try:
                load_sqlite_vec(connection)
                row = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'chunk_vectors'"
                ).fetchone()
                if row is None:
                    problems.append(f"{vault_dir.name}: metadata.sqlite missing chunk_vectors")
                else:
                    ready += 1
            finally:
                connection.close()
        except Exception as error:
            problems.append(f"{vault_dir.name}: cannot open metadata.sqlite ({error})")

    if problems:
        return DoctorCheck(
            name="index",
            status=CheckStatus.FAIL,
            message="Index corruption signals: " + "; ".join(problems),
            recommendation="Run a full reindex from the plugin Status view.",
        )
    if ready == 0:
        message = f"Found {len(vault_dirs)} vault dir(s) but none look indexed"
        if warnings:
            message += "; " + "; ".join(warnings)
        return DoctorCheck(
            name="index",
            status=CheckStatus.WARN,
            message=message,
            recommendation="Run a full sync/index from the plugin.",
        )
    if warnings:
        return DoctorCheck(
            name="index",
            status=CheckStatus.WARN,
            message=f"{ready} vault index(es) look present; " + "; ".join(warnings),
            recommendation="Remove legacy qdrant/ directories and run a full reindex.",
        )
    return DoctorCheck(
        name="index",
        status=CheckStatus.OK,
        message=f"{ready} vault index(es) look present",
        recommendation="",
    )


def check_memory(
    *,
    available_bytes: int | None = None,
) -> DoctorCheck:
    free = available_bytes if available_bytes is not None else _available_memory_bytes()
    if free is None:
        return DoctorCheck(
            name="memory",
            status=CheckStatus.WARN,
            message="Could not determine available memory on this platform",
            recommendation="Ensure at least 2 GiB free RAM before indexing large vaults.",
        )
    human = _format_bytes(free)
    if free < MEMORY_WARN_BYTES:
        return DoctorCheck(
            name="memory",
            status=CheckStatus.WARN,
            message=f"Only {human} available (below 2 GiB)",
            recommendation="Close other apps or free memory before heavy indexing.",
        )
    return DoctorCheck(
        name="memory",
        status=CheckStatus.OK,
        message=f"{human} available",
        recommendation="",
    )


def _available_memory_bytes() -> int | None:
    system = platform.system()
    if system == "Linux":
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("MemAvailable:"):
                    parts = line.split()
                    return int(parts[1]) * 1024
        except OSError:
            return None
    if system == "Darwin":
        try:
            vm = subprocess.run(
                ["vm_stat"],
                check=True,
                capture_output=True,
                text=True,
            )
            page_size = 4096
            free_pages = 0
            for line in vm.stdout.splitlines():
                if "page size of" in line:
                    tokens = line.split()
                    for token in tokens:
                        if token.isdigit():
                            page_size = int(token)
                if line.startswith("Pages free:") or line.startswith("Pages speculative:"):
                    value = line.split(":")[1].strip().rstrip(".")
                    free_pages += int(value)
            if free_pages > 0:
                return free_pages * page_size
            total = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                check=True,
                capture_output=True,
                text=True,
            )
            return int(total.stdout.strip()) // 4
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
    if system == "Windows":
        try:
            import ctypes
            from ctypes import wintypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if not kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return None
            return int(stat.ullAvailPhys)
        except Exception:
            return None
    return None


def _format_bytes(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"
