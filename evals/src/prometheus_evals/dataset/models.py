"""Pydantic models for depersonalized evaluation corpora."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ExpectedSource(BaseModel, frozen=True):
    path: str
    heading: str | None = None

    @field_validator("path")
    @classmethod
    def path_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("path cannot be blank")
        return value


class EvalDocument(BaseModel, frozen=True):
    relative_path: str
    content: str

    @field_validator("relative_path")
    @classmethod
    def path_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("relative_path cannot be blank")
        return value


class EvalQuestion(BaseModel, frozen=True):
    id: str
    question: str
    kind: Literal["answerable", "unanswerable"]
    expected_sources: tuple[ExpectedSource, ...] = ()
    reference_keywords: tuple[str, ...] = ()

    @field_validator("id", "question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field cannot be blank")
        return value


class DatasetManifest(BaseModel, frozen=True):
    dataset_id: str
    version: str
    language_mix: str
    description: str


class EvalDataset(BaseModel, frozen=True):
    manifest: DatasetManifest
    documents: tuple[EvalDocument, ...]
    questions: tuple[EvalQuestion, ...]
    root: str = Field(description="Absolute path to the dataset directory")
