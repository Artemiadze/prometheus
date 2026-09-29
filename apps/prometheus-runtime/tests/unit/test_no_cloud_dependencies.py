"""Regression test for the local-only runtime dependency policy."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

PROHIBITED_PACKAGES = frozenset(
    {
        "anthropic",
        "azure-ai-inference",
        "cohere",
        "google-generativeai",
        "google-genai",
        "mistralai",
        "openai",
        "voyageai",
    }
)
PROHIBITED_IMPORT_ROOTS = frozenset(
    {
        "anthropic",
        "cohere",
        "openai",
        "voyageai",
        "mistralai",
        "google.generativeai",
        "google.genai",
    }
)
PROHIBITED_HTTPS_MARKERS = frozenset(
    {
        "https://api.openai.com",
        "https://api.anthropic.com",
        "https://api.cohere.ai",
        "https://generativelanguage.googleapis.com",
    }
)


def _package_name(dependency: str) -> str:
    name = dependency.split(";", 1)[0].strip()
    for separator in (">=", "==", "~=", "<=", "!="):
        name = name.split(separator, 1)[0]
    return name.strip().casefold()


def test_runtime_declares_no_cloud_llm_or_embedding_sdk() -> None:
    project_file = Path(__file__).parents[2] / "pyproject.toml"
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))["project"]
    package_names = {_package_name(dependency) for dependency in project["dependencies"]}

    assert package_names.isdisjoint(PROHIBITED_PACKAGES)


def test_lockfile_and_installed_distributions_exclude_cloud_sdks() -> None:
    root = Path(__file__).parents[2]
    lock_text = (root / "uv.lock").read_text(encoding="utf-8").casefold()
    for package in PROHIBITED_PACKAGES:
        assert f'name = "{package}"' not in lock_text

    site_packages = root / ".venv" / "lib"
    installed = {
        path.name.casefold()
        for path in site_packages.glob("python*/site-packages/*")
        if path.is_dir() or path.suffix == ".dist-info"
    }
    for package in PROHIBITED_PACKAGES:
        assert not any(package in name for name in installed)


def test_source_tree_has_no_cloud_imports_or_https_llm_endpoints() -> None:
    src_root = Path(__file__).parents[2] / "src"
    for path in src_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for marker in PROHIBITED_HTTPS_MARKERS:
            assert marker not in source, path
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                names = [node.module]
            else:
                continue
            for name in names:
                assert not any(
                    name == prohibited or name.startswith(f"{prohibited}.")
                    for prohibited in PROHIBITED_IMPORT_ROOTS
                ), f"{path}: {name}"
