"""Answer a question using only retrieved Vault context."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator

from application.dto.answer_stream import AnswerCompletedEvent, AnswerTokenEvent
from application.dto.grounded_prompt import GroundedPrompt
from application.errors import GroundedAnswerGenerationError
from application.ports.language_model import LanguageModel
from application.ports.token_counter import TokenCounter
from application.services.answer_cache import AnswerCache, CachedAnswer
from application.services.answer_contract import (
    ANSWER_SCHEMA,
    AnswerStreamExtractor,
    ParsedAnswer,
    try_parse_answer,
)
from application.services.answer_language import detect_language, insufficient_message
from application.services.compute_gate import ComputeGate
from application.services.degenerate_stream import DegenerateStreamError, DegenerateStreamGuard
from application.services.grounded_prompt import build_grounded_prompt
from application.services.index_generation import IndexGeneration
from application.services.retrieval import RetrievalService
from domain.entities.grounded_answer import GroundedAnswer
from domain.services.grounding_policy import GroundingPolicy
from domain.value_objects.chunk_id import ChunkId
from domain.value_objects.search_scope import SearchScope
from domain.value_objects.source_reference import SourceReference


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
        llm_model: str,
        compute_gate: ComputeGate | None = None,
        answer_cache: AnswerCache | None = None,
        index_generation: IndexGeneration | None = None,
    ) -> None:
        self._retrieval = retrieval
        self._policy = grounding_policy
        self._tokens = token_counter
        self._llm = language_model
        self._context_size = context_size
        self._reserve = response_token_reserve
        self._temperature = temperature
        self._llm_model = llm_model
        self._compute_gate = compute_gate or ComputeGate()
        self._answer_cache = answer_cache
        self._index_generation = index_generation

    async def execute(
        self,
        question: str,
        *,
        scope: SearchScope | None = None,
        limit: int,
    ) -> GroundedAnswer:
        cache_key = _cache_key(
            question,
            scope,
            limit,
            self._llm_model,
            self._index_generation.value if self._index_generation else 0,
        )
        cached = self._answer_cache.get(cache_key) if self._answer_cache else None
        if cached is not None:
            return _answer_from_cache(cached)

        prompt = await self._prepare(question, scope=scope, limit=limit)
        if prompt is None:
            return _insufficient_answer(question)
        async with self._compute_gate.exclusive("foreground"):
            parsed = await self._generate_parsed(prompt)
        sources, chunk_ids = _resolve_citations(prompt, parsed.cited)
        answer = GroundedAnswer.create(
            text=parsed.text,
            sources=sources,
            used_chunk_ids=chunk_ids,
            insufficient_context=False,
        )
        if self._answer_cache is not None:
            self._answer_cache.put(cache_key, answer)
        return answer

    async def stream(
        self,
        question: str,
        *,
        scope: SearchScope | None = None,
        limit: int,
    ) -> AsyncIterator[AnswerTokenEvent | AnswerCompletedEvent]:
        cache_key = _cache_key(
            question,
            scope,
            limit,
            self._llm_model,
            self._index_generation.value if self._index_generation else 0,
        )
        cached = self._answer_cache.get(cache_key) if self._answer_cache else None
        if cached is not None:
            yield AnswerTokenEvent(text=cached.text)
            yield AnswerCompletedEvent(
                sources=cached.sources,
                insufficient_context=cached.insufficient_context,
            )
            return

        prompt = await self._prepare(question, scope=scope, limit=limit)
        if prompt is None:
            yield AnswerCompletedEvent(sources=(), insufficient_context=True)
            return

        extractor = AnswerStreamExtractor()
        guard = DegenerateStreamGuard()
        try:
            async with self._compute_gate.exclusive("foreground"):
                async for token in self._llm.stream(
                    prompt.system,
                    prompt.user,
                    temperature=self._temperature,
                    context_size=self._context_size,
                    max_output_tokens=self._reserve,
                    response_schema=ANSWER_SCHEMA,
                ):
                    guard.check(token)
                    visible = extractor.feed(token)
                    if visible:
                        yield AnswerTokenEvent(text=visible)
        except DegenerateStreamError as error:
            raise GroundedAnswerGenerationError() from error

        parsed = try_parse_answer(extractor.finish(), len(prompt.included_chunks))
        if parsed is None:
            sources = prompt.sources
            chunk_ids = tuple(chunk.id for chunk in prompt.included_chunks)
            answer_text = ""
        else:
            sources, chunk_ids = _resolve_citations(prompt, parsed.cited)
            answer_text = parsed.text
        yield AnswerCompletedEvent(sources=sources, insufficient_context=False)

        if parsed is not None and self._answer_cache is not None and answer_text:
            self._answer_cache.put(
                cache_key,
                GroundedAnswer.create(
                    text=answer_text,
                    sources=sources,
                    used_chunk_ids=chunk_ids,
                    insufficient_context=False,
                ),
            )

    async def _generate_parsed(self, prompt: GroundedPrompt) -> ParsedAnswer:
        generation = await self._llm.generate(
            prompt.system,
            prompt.user,
            temperature=self._temperature,
            context_size=self._context_size,
            max_output_tokens=self._reserve,
            response_schema=ANSWER_SCHEMA,
        )
        parsed = try_parse_answer(generation.text, len(prompt.included_chunks))
        if parsed is None:
            raise GroundedAnswerGenerationError()
        return parsed

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


def _scope_cache_key(scope: SearchScope | None) -> str:
    if scope is None:
        return "entire"
    folders = ",".join(sorted(folder.value for folder in scope.folders))
    excluded = ",".join(sorted(folder.value for folder in scope.excluded_folders))
    note = scope.note.value if scope.note is not None else ""
    return f"{scope.mode.value}|{note}|{folders}|{excluded}"


def _cache_key(
    question: str,
    scope: SearchScope | None,
    limit: int,
    model: str,
    index_generation: int,
) -> str:
    payload = f"{question.strip()}|{_scope_cache_key(scope)}|{limit}|{model}|{index_generation}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _answer_from_cache(cached: CachedAnswer) -> GroundedAnswer:
    return GroundedAnswer.create(
        text=cached.text,
        sources=cached.sources,
        used_chunk_ids=cached.used_chunk_ids,
        insufficient_context=cached.insufficient_context,
    )
