"""Streaming behavior of the LanguageModel test fake."""

from __future__ import annotations

import asyncio

from fakes import FakeLanguageModel


def test_fake_language_model_marks_stream_closed_when_consumer_stops_early() -> None:
    llm = FakeLanguageModel(stream_parts=("only", "blocked"))

    async def read_one() -> str:
        token = ""
        async for piece in llm.stream(
            "prompt",
            temperature=0.1,
            context_size=1024,
            max_output_tokens=128,
        ):
            token = piece
            break
        return token

    token = asyncio.run(read_one())
    assert token == "only"
    assert llm.stream_closed
