"""Tests for answer language detection and localized insufficiency messages."""

from __future__ import annotations

from application.services.answer_language import (
    build_system_instruction,
    detect_language,
    insufficient_message,
)


def test_detect_language_prefers_cyrillic_for_mixed_questions() -> None:
    assert detect_language("Как запустить sqlite?") == "ru"


def test_detect_language_returns_none_for_code_only_questions() -> None:
    assert detect_language("??? 123") is None


def test_insufficient_message_is_localized() -> None:
    assert "заметках" in insufficient_message("ru")
    assert insufficient_message("en").startswith("The notes")


def test_build_system_instruction_uses_explicit_language_when_known() -> None:
    assert "Отвечай на русском языке." in build_system_instruction("ru")
    assert "Reply in English." in build_system_instruction("en")
