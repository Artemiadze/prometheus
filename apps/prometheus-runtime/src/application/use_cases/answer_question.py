"""Answer a question using only retrieved Vault context."""

from __future__ import annotations

from collections.abc import AsyncIterator

from application.dto.answer_stream import AnswerCompletedEvent, AnswerTokenEvent
from application.dto.grounded_prompt import GroundedPrompt
from application.errors import GroundedAnswerGenerationError
from application.ports.language_model import LanguageModel
from application.ports.token_counter import TokenCounter
from application.services.answer_contract import (
    ANSWER_SCHEMA,
    AnswerParseError,
    AnswerStreamExtractor,
    ParsedAnswer,
    parse_answer,
)
from application.services.answer_language import detect_language, insufficient_message
from application.services.grounded_prompt import build_grounded_prompt
from application.services.retrieval import RetrievalService
from domain.entities.grounded_answer import GroundedAnswer
from domain.services.grounding_policy import GroundingPolicy
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.search_scope import SearchScope
from domain.value_objects.source_reference import SourceReference

_REPAIR_PREFIX = (
    "\n\nRepair: return valid JSON with a non-empty answer and a sources array. " "Previous error:"
)


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
        prompt = await self._prepare(question, scope=scope, limit=limit)
        if prompt is None:
            return _insufficient_answer(question)
        parsed = await self._generate_parsed(prompt)
        sources, chunk_ids = _resolve_citations(prompt, parsed.cited)
        return GroundedAnswer.create(
            text=parsed.text,
            sources=sources,
            used_chunk_ids=chunk_ids,
            insufficient_context=False,
        )

    async def stream(
        self,
        question: str,
        *,
        scope: SearchScope | None = None,
        limit: int,
    ) -> AsyncIterator[AnswerTokenEvent | AnswerCompletedEvent]:
        prompt = await self._prepare(question, scope=scope, limit=limit)
        if prompt is None:
            yield AnswerCompletedEvent(sources=(), insufficient_context=True)
            return

        extractor = AnswerStreamExtractor()
        async for token in self._llm.stream(
            prompt.system,
            prompt.user,
            temperature=self._temperature,
            context_size=self._context_size,
            max_output_tokens=self._reserve,
            response_schema=ANSWER_SCHEMA,
        ):
            visible = extractor.feed(token)
            if visible:
                yield AnswerTokenEvent(text=visible)

        try:
            parsed = parse_answer(extractor.finish(), len(prompt.included_chunks))
            sources, _ = _resolve_citations(prompt, parsed.cited)
        except AnswerParseError:
            sources = prompt.sources
        yield AnswerCompletedEvent(sources=sources, insufficient_context=False)

    async def _generate_parsed(self, prompt: GroundedPrompt) -> ParsedAnswer:
        repair_error = ""
        for attempt in range(2):
            user = prompt.user if attempt == 0 else f"{prompt.user}{_REPAIR_PREFIX} {repair_error}"
            generation = await self._llm.generate(
                prompt.system,
                user,
                temperature=self._temperature,
                context_size=self._context_size,
                max_output_tokens=self._reserve,
                response_schema=ANSWER_SCHEMA,
            )
            try:
                return parse_answer(generation.text, len(prompt.included_chunks))
            except AnswerParseError as error:
                repair_error = str(error)
        raise GroundedAnswerGenerationError()

    async def _prepare(
        self,
        question: str,
        *,
        scope: SearchScope | None,
        limit: int,
    ) -> GroundedPrompt | None:
        retrieved = await self._retrieval.retrieve(question, scope=scope, limit=limit)
        selection = self._policy.select_context(item.hit for item in retrieved)
        if selection.insufficient_context:
            return None
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
            return None
        return prompt


def _insufficient_answer(question: str) -> GroundedAnswer:
    return GroundedAnswer.create(
        text=insufficient_message(detect_language(question)),
        insufficient_context=True,
    )


def _resolve_citations(
    prompt: GroundedPrompt,
    cited: tuple[int, ...],
) -> tuple[tuple[SourceReference, ...], tuple[ChunkId, ...]]:
    if not cited:
        return prompt.sources, tuple(chunk.id for chunk in prompt.included_chunks)
    sources: list[SourceReference] = []
    chunk_ids: list[ChunkId] = []
    for index in cited:
        position = index - 1
        sources.append(prompt.sources[position])
        chunk_ids.append(prompt.included_chunks[position].id)
    return tuple(sources), tuple(chunk_ids)
