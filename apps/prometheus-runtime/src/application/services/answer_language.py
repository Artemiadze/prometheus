"""Detect answer language and build grounded-chat system instructions."""

from __future__ import annotations

from typing import Literal

AnswerLanguage = Literal["ru", "en"]


def detect_language(question: str) -> AnswerLanguage | None:
    """Return the dominant script in the question, or None when neither is present."""

    cyrillic = sum(1 for char in question if "\u0400" <= char <= "\u04ff")
    latin = sum(1 for char in question if char.isascii() and char.isalpha())
    if cyrillic == 0 and latin == 0:
        return None
    if cyrillic >= latin:
        return "ru"
    return "en"


def build_system_instruction(language: AnswerLanguage | None) -> str:
    if language == "ru":
        language_rule = "Отвечай на русском языке."
        insufficiency = "скажи, что в заметках пользователя недостаточно информации"
    elif language == "en":
        language_rule = "Reply in English."
        insufficiency = "say that there is not enough information in the user's notes"
    else:
        language_rule = "Reply in the same language as the question."
        insufficiency = "say that there is not enough information in the user's notes"

    return f"""Answer using only the context fragments in the user message.
If the answer is not in the context, {insufficiency}. Do not use outside knowledge.

{language_rule}

Output JSON with "answer" and "sources" (enforced by the response format):
- "answer": the user-facing reply; put commands, code, and exact values in fenced code blocks.
- "sources": 1-based fragment numbers you used, in first-use order."""


def insufficient_message(language: AnswerLanguage | None) -> str:
    if language == "ru":
        return "В заметках недостаточно информации, чтобы ответить на этот вопрос."
    return "The notes do not contain enough information to answer this question."
