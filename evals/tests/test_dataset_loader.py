"""Dataset loader and PII validation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from prometheus_evals.dataset.loader import DatasetValidationError, load_dataset
from prometheus_evals.dataset.pii import assert_no_pii, find_pii_violations

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "synthetic_v1"


def test_load_synthetic_v1_dataset() -> None:
    dataset = load_dataset(DATASET)
    assert dataset.manifest.dataset_id == "synthetic_v1"
    assert len(dataset.documents) >= 40
    answerable = [q for q in dataset.questions if q.kind == "answerable"]
    unanswerable = [q for q in dataset.questions if q.kind == "unanswerable"]
    assert len(answerable) >= 30
    assert len(unanswerable) >= 10


def test_loader_rejects_missing_source_path(tmp_path: Path) -> None:
    root = tmp_path / "broken"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "a.md").write_text("# Title\n\nBody\n", encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": "x",
                "version": "1",
                "language_mix": "en",
                "description": "test",
            }
        ),
        encoding="utf-8",
    )
    (root / "questions.jsonl").write_text(
        json.dumps(
            {
                "id": "q1",
                "question": "Where?",
                "kind": "answerable",
                "expected_sources": [{"path": "notes/missing.md"}],
                "reference_keywords": ["Body"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(DatasetValidationError):
        load_dataset(root)


def test_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    root = tmp_path / "dup"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "a.md").write_text("# H\n\nText\n", encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "dataset_id": "x",
                "version": "1",
                "language_mix": "en",
                "description": "test",
            }
        ),
        encoding="utf-8",
    )
    line = json.dumps(
        {
            "id": "dup",
            "question": "Q?",
            "kind": "unanswerable",
            "expected_sources": [],
            "reference_keywords": [],
        }
    )
    (root / "questions.jsonl").write_text(f"{line}\n{line}\n", encoding="utf-8")
    with pytest.raises(DatasetValidationError):
        load_dataset(root)


def test_pii_scanner_flags_email() -> None:
    violations = find_pii_violations("Contact me at person@example.com please")
    assert violations
    with pytest.raises(ValueError):
        assert_no_pii(["Contact me at person@example.com please"])
