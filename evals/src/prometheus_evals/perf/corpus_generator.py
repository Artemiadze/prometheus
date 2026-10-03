"""Deterministic synthetic corpora for performance benchmarks."""

from __future__ import annotations

import hashlib
from pathlib import Path

from prometheus_evals.dataset.models import EvalDocument

_SCALE_TARGETS = {
    "small": 200,
    "full": 4000,
}


def note_count_for_scale(scale: str) -> int:
    try:
        return _SCALE_TARGETS[scale]
    except KeyError as error:
        raise ValueError(f"unknown scale {scale!r}; expected small or full") from error


def generate_perf_corpus(*, scale: str, seed: int = 42) -> tuple[EvalDocument, ...]:
    count = note_count_for_scale(scale)
    documents: list[EvalDocument] = []
    for index in range(count):
        token = _token_for(index, seed)
        topic = _topic_for(index)
        path = f"notes/perf/{topic}/note_{index:05d}.md"
        content = _render_note(index=index, token=token, topic=topic)
        documents.append(EvalDocument(relative_path=path, content=content))
    return tuple(documents)


def materialize_perf_corpus(target_dir: Path, *, scale: str, seed: int = 42) -> Path:
    root = target_dir / f"generated_{scale}"
    notes_dir = root / "notes" / "perf"
    notes_dir.mkdir(parents=True, exist_ok=True)
    for document in generate_perf_corpus(scale=scale, seed=seed):
        path = root / document.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document.content, encoding="utf-8")
    return root


def _token_for(index: int, seed: int) -> str:
    digest = hashlib.sha256(f"{seed}:{index}".encode()).hexdigest()
    return digest[:12]


def _topic_for(index: int) -> str:
    topics = ("python", "recipes", "projects", "research", "notes")
    return topics[index % len(topics)]


def _render_note(*, index: int, token: str, topic: str) -> str:
    paragraphs = []
    for part in range(8):
        paragraphs.append(
            f"Paragraph {part} in synthetic {topic} note {index}. "
            f"Marker token {token} appears here for retrieval benchmarks. "
            "This text repeats domain terms like indexing, chunking, and embeddings "
            "to approximate real vault note density without personal data."
        )
    body = "\n\n".join(paragraphs)
    return f"# Synthetic {topic.title()} {index}\n\n{body}\n"
