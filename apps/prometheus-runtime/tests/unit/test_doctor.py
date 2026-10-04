"""Unit tests for read-only doctor diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from bootstrap.doctor import (
    CheckStatus,
    check_data_dir,
    check_embedding_model,
    check_index,
    check_memory,
    check_ollama,
    doctor_exit_code,
    format_doctor_report,
)


def test_format_and_exit_code() -> None:
    from bootstrap.doctor import DoctorCheck

    checks = [
        DoctorCheck("a", CheckStatus.OK, "ok", ""),
        DoctorCheck("b", CheckStatus.WARN, "warn", "fix it"),
        DoctorCheck("c", CheckStatus.FAIL, "fail", "reindex"),
    ]
    report = format_doctor_report(checks)
    assert "[FAIL] c" in report
    assert "recommendation: reindex" in report
    assert "1 failing, 1 warning(s)" in report
    assert doctor_exit_code(checks) == 1
    assert doctor_exit_code(checks[:2]) == 0


def test_data_dir_missing_is_warn(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    result = check_data_dir(missing)
    assert result.status is CheckStatus.WARN
    assert "does not exist" in result.message


def test_data_dir_ok(tmp_path: Path) -> None:
    result = check_data_dir(tmp_path)
    assert result.status is CheckStatus.OK


def test_data_dir_file_is_fail(tmp_path: Path) -> None:
    path = tmp_path / "not-a-dir"
    path.write_text("x", encoding="utf-8")
    result = check_data_dir(path)
    assert result.status is CheckStatus.FAIL


def test_ollama_unreachable() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    def factory() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))

    result = check_ollama("http://127.0.0.1:11434", "qwen3:4b", client_factory=factory)
    assert result.status is CheckStatus.WARN
    assert "unreachable" in result.message


def test_ollama_missing_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "other:1b"}]})

    def factory() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))

    result = check_ollama("http://127.0.0.1:11434", "qwen3:4b", client_factory=factory)
    assert result.status is CheckStatus.WARN
    assert "not found" in result.message


def test_ollama_ok() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})

    def factory() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))

    result = check_ollama("http://127.0.0.1:11434", "qwen3:4b", client_factory=factory)
    assert result.status is CheckStatus.OK


def test_embedding_missing_fail(tmp_path: Path) -> None:
    result = check_embedding_model(
        tmp_path, "intfloat/multilingual-e5-large", allow_download=False
    )
    assert result.status is CheckStatus.FAIL


def test_embedding_missing_warn_when_download_allowed(tmp_path: Path) -> None:
    result = check_embedding_model(
        tmp_path, "intfloat/multilingual-e5-large", allow_download=True
    )
    assert result.status is CheckStatus.WARN


def test_embedding_present(tmp_path: Path) -> None:
    cache = (
        tmp_path / "models" / "embeddings" / "models--intfloat--multilingual-e5-large"
    )
    cache.mkdir(parents=True)
    (cache / "model.onnx").write_bytes(b"x")
    result = check_embedding_model(
        tmp_path, "intfloat/multilingual-e5-large", allow_download=False
    )
    assert result.status is CheckStatus.OK


def test_index_not_indexed(tmp_path: Path) -> None:
    result = check_index(tmp_path)
    assert result.status is CheckStatus.WARN
    assert "not indexed" in result.message


def test_index_corrupted(tmp_path: Path) -> None:
    vault = tmp_path / "vaults" / "vault-a"
    vault.mkdir(parents=True)
    (vault / "qdrant_metadata.json").write_text("{}", encoding="utf-8")
    result = check_index(tmp_path)
    assert result.status is CheckStatus.FAIL
    assert "corruption" in result.message.casefold()


def test_index_ready(tmp_path: Path) -> None:
    vault = tmp_path / "vaults" / "vault-a"
    storage = vault / "qdrant"
    storage.mkdir(parents=True)
    (storage / "collection").write_text("x", encoding="utf-8")
    (vault / "qdrant_metadata.json").write_text("{}", encoding="utf-8")
    result = check_index(tmp_path)
    assert result.status is CheckStatus.OK


def test_memory_low() -> None:
    result = check_memory(available_bytes=512 * 1024 * 1024)
    assert result.status is CheckStatus.WARN
    assert "below 2 GiB" in result.message


def test_memory_ok() -> None:
    result = check_memory(available_bytes=8 * 1024 * 1024 * 1024)
    assert result.status is CheckStatus.OK


def test_doctor_does_not_create_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bootstrap import doctor as doctor_module
    from bootstrap.config import RuntimeSettings

    created: list[Any] = []

    def boom(*_args: object, **_kwargs: object) -> None:
        created.append(True)
        raise AssertionError("must not create layout")

    monkeypatch.setattr("adapters.outbound.filesystem.data_dir.ensure_layout", boom)
    missing = tmp_path / "fresh-data"
    settings = RuntimeSettings(data_dir=missing)
    checks = doctor_module.run_doctor(settings)
    assert created == []
    assert not missing.exists()
    assert any(check.name == "data_dir" for check in checks)
