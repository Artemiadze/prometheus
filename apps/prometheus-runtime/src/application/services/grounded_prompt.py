"""Build BR-4 prompts while preserving an exact token budget and source set."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from application.dto.grounded_prompt import GroundedPrompt
from application.ports.token_counter import TokenCounter
from domain.entities.chunk import Chunk
from domain.errors import InvariantViolationError
from domain.value_objects.document_id import DocumentId
from domain.value_objects.relative_path import RelativePath
from domain.value_objects.source_reference import SourceReference

_INSTRUCTION = """Answer using only the provided context.
If the information required to answer the question is not present in the context,
say that there is not enough information in the user's notes.
Do not use outside knowledge."""


def build_grounded_prompt(
    *,
    question: str,
    chunks: Sequence[Chunk],
    document_paths: Mapping[DocumentId, RelativePath],
    token_counter: TokenCounter,
    context_size: int,
    response_token_reserve: int,
) -> GroundedPrompt:
    """Select whole chunks greedily and return the exact prompt and source set.

    Chunks retain their input order, which is expected to be retrieval/reranking
    order. A chunk that does not fit is skipped so a smaller later chunk may still
    use the remaining budget.
    """

    if not question.strip():
        raise ValueError("question cannot be blank")
    if context_size <= 0 or response_token_reserve <= 0 or response_token_reserve >= context_size:
        raise ValueError("invalid LLM token budget")

    prompt_budget = context_size - response_token_reserve
    included: list[Chunk] = []
    sources: list[SourceReference] = []
    prompt = _render_prompt(question, (), (), no_context=True)
    token_count = token_counter.count(prompt)
    if token_count > prompt_budget:
        raise ValueError("prompt overhead exceeds LLM token budget")

    for chunk in chunks:
        try:
            path = document_paths[chunk.document_id]
        except KeyError as error:
            raise InvariantViolationError() from error
        source = SourceReference(path, chunk.heading)
        candidate_chunks = (*included, chunk)
        candidate_sources = (*sources, source)
        candidate = _render_prompt(
            question,
            candidate_chunks,
            candidate_sources,
            no_context=False,
        )
        candidate_count = token_counter.count(candidate)
        if candidate_count > prompt_budget:
            continue
        included.append(chunk)
        sources.append(source)
        prompt = candidate
        token_count = candidate_count

    return GroundedPrompt(
        text=prompt,
        included_chunks=tuple(included),
        sources=tuple(sources),
        token_count=token_count,
    )


def _render_prompt(
    question: str,
    chunks: Sequence[Chunk],
    sources: Sequence[SourceReference],
    *,
    no_context: bool,
) -> str:
    if no_context:
        context = "No context fragments were included."
    else:
        context = "\n\n".join(
            _render_fragment(index, chunk, source)
            for index, (chunk, source) in enumerate(
                zip(chunks, sources, strict=True),
                start=1,
            )
        )
    return f"{_INSTRUCTION}\n\nContext:\n{context}\n\nQuestion:\n{question.strip()}\n\nAnswer:"


def _render_fragment(index: int, chunk: Chunk, source: SourceReference) -> str:
    label = source.relative_path.value
    if source.heading is not None:
        label = f"{label}#{source.heading}"
    return f"[{index}] Source: {label}\n{chunk.text}"
