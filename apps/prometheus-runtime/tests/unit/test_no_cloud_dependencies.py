"""Regression test for the local-only runtime dependency policy."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_runtime_declares_no_cloud_llm_or_embedding_sdk() -> None:
    project_file = Path(__file__).parents[2] / "pyproject.toml"
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))["project"]
    dependencies = project["dependencies"]
    package_names = {
        dependency.split(">=", 1)[0].split("==", 1)[0].casefold() for dependency in dependencies
    }

    prohibited = {
        "anthropic",
        "azure-ai-inference",
        "cohere",
        "google-generativeai",
        "google-genai",
        "mistralai",
        "openai",
        "voyageai",
    }
    assert package_names.isdisjoint(prohibited)
