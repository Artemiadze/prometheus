"""Answer a question using only retrieved Vault context."""

from application.ports.language_model import LanguageModel
from application.ports.token_counter import TokenCounter
from application.services.grounded_prompt import build_grounded_prompt
from application.services.retrieval import RetrievalService
from domain.entities.grounded_answer import GroundedAnswer
from domain.services.grounding_policy import GroundingPolicy
from domain.value_objects.search_scope import SearchScope

_INSUFFICIENT_MESSAGE = "The notes do not contain enough information to answer this question."


class AnswerQuestion:
    def __init__(
        self,
        *,
        retrieval: RetrievalService,
        grounding_policy: GroundingPolicy,
        token_counter: TokenCounter,
        language_model: LanguageModel,
        context_size: int,
        response_token_reserve: int,
        temperature: float,
    ) -> None:
        self._retrieval = retrieval
        self._policy = grounding_policy
        self._tokens = token_counter
        self._llm = language_model
        self._context_size = context_size
        self._reserve = response_token_reserve
        self._temperature = temperature

    async def execute(
        self,
        question: str,
        *,
        scope: SearchScope | None = None,
        limit: int,
    ) -> GroundedAnswer:
        retrieved = await self._retrieval.retrieve(question, scope=scope, limit=limit)
        selection = self._policy.select_context(item.hit for item in retrieved)
        if selection.insufficient_context:
            return _insufficient_answer()
        paths = {item.hit.chunk.document_id: item.relative_path for item in retrieved}
        prompt = build_grounded_prompt(
            question=question,
            chunks=tuple(hit.chunk for hit in selection.hits),
            document_paths=paths,
            token_counter=self._tokens,
            context_size=self._context_size,
            response_token_reserve=self._reserve,
        )
        if not prompt.included_chunks:
            return _insufficient_answer()
        generation = await self._llm.generate(
            prompt.text,
            temperature=self._temperature,
            context_size=self._context_size,
            max_output_tokens=self._reserve,
        )
        return GroundedAnswer.create(
            text=generation.text,
            sources=prompt.sources,
            used_chunk_ids=(chunk.id for chunk in prompt.included_chunks),
            insufficient_context=False,
        )


def _insufficient_answer() -> GroundedAnswer:
    return GroundedAnswer.create(text=_INSUFFICIENT_MESSAGE, insufficient_context=True)
