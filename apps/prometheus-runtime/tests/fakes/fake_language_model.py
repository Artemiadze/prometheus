"""Predictable local LanguageModel fake."""

from collections.abc import Sequence

from domain.entities.chunk import Chunk


class FakeLanguageModel:
    """Echo questions and context while recording generation calls."""

    def __init__(
        self,
        models: Sequence[str] = ("fake-model",),
        *,
        available: bool = True,
    ) -> None:
        self.models = tuple(models)
        self.available = available
        self.calls: list[tuple[str, tuple[Chunk, ...], float, int]] = []

    def generate(
        self,
        question: str,
        context: Sequence[Chunk],
        *,
        temperature: float,
        context_size: int,
    ) -> str:
        chunks = tuple(context)
        self.calls.append((question, chunks, temperature, context_size))
        context_text = "\n".join(chunk.text for chunk in chunks)
        return f"Question: {question}\nContext:\n{context_text}"

    def list_models(self) -> Sequence[str]:
        return self.models

    def is_available(self) -> bool:
        return self.available
