"""Predictable local LanguageModel fake."""

from collections.abc import Sequence

from application.dto.llm import LlmGeneration, LocalLlmModel


class FakeLanguageModel:
    """Echo questions and context while recording generation calls."""

    def __init__(
        self,
        models: Sequence[LocalLlmModel] = (LocalLlmModel("fake-model", 0),),
        *,
        available: bool = True,
    ) -> None:
        self.models = tuple(models)
        self.available = available
        self.calls: list[tuple[str, float, int, int]] = []

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float,
        context_size: int,
        max_output_tokens: int,
    ) -> LlmGeneration:
        self.calls.append((prompt, temperature, context_size, max_output_tokens))
        model = self.models[0].name if self.models else "fake-model"
        return LlmGeneration(prompt, model)

    async def list_models(self) -> Sequence[LocalLlmModel]:
        return self.models

    async def is_available(self) -> bool:
        return self.available
