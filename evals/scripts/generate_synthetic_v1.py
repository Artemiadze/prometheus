#!/usr/bin/env python3
"""Generate the synthetic_v1 evaluation corpus (depersonalized)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "datasets" / "synthetic_v1"

TOPICS: list[tuple[str, str, str]] = [
    ("python/async.md", "Async Python", "asyncio gather tasks coroutines"),
    ("python/types.md", "Typing Basics", "mypy strict dataclasses protocols"),
    ("python/testing.md", "Testing Notes", "pytest fixtures markers coverage"),
    ("python/packaging.md", "Packaging", "hatchling uv wheel sdist"),
    ("recipes/pasta.md", "Pasta Night", "tomato basil garlic olive oil"),
    ("recipes/soup.md", "Winter Soup", "carrot potato broth thyme"),
    ("recipes/salad.md", "Garden Salad", "cucumber lettuce vinegar dressing"),
    ("recipes/bread.md", "Sourdough", "starter fermentation crust scoring"),
    ("projects/alpha.md", "Project Alpha", "kanban roadmap milestone demo"),
    ("projects/beta.md", "Project Beta", "prototype feedback iteration release"),
    ("projects/gamma.md", "Project Gamma", "budget timeline stakeholder review"),
    ("projects/delta.md", "Project Delta", "architecture diagram module boundary"),
    ("research/rag.md", "RAG Research", "retrieval grounding citations chunks"),
    ("research/embeddings.md", "Embeddings", "cosine similarity vector index"),
    ("research/evals.md", "Eval Metrics", "recall mrr ndcg benchmark"),
    ("research/security.md", "Security Notes", "sandbox token session localhost"),
    ("journal/travel.md", "Travel Plan", "itinerary museum train reservation"),
    ("journal/books.md", "Reading List", "novel essay library bookmark"),
    ("journal/music.md", "Music Log", "album concert playlist rehearsal"),
    ("journal/fitness.md", "Fitness Log", "stretching run hydration schedule"),
    ("python/cli.md", "CLI Patterns", "typer commands options help"),
    ("python/logging.md", "Logging", "structured logs levels handlers"),
    ("python/config.md", "Configuration", "pydantic settings environment overrides"),
    ("python/errors.md", "Error Handling", "domain errors envelopes mapping"),
    ("recipes/tea.md", "Tea Notes", "oolong steep temperature kettle"),
    ("recipes/cookies.md", "Cookies", "butter sugar oven baking sheet"),
    ("recipes/rice.md", "Rice Bowl", "soy sesame scallion bowl"),
    ("recipes/stew.md", "Hearty Stew", "beans simmer bay leaf pot"),
    ("projects/epsilon.md", "Project Epsilon", "migration rollout checklist"),
    ("projects/zeta.md", "Project Zeta", "design review notes action items"),
    ("projects/eta.md", "Project Eta", "performance profiling flamegraph"),
    ("projects/theta.md", "Project Theta", "documentation outline tutorial"),
    ("research/obsidian.md", "Obsidian Notes", "markdown links backlinks graph"),
    ("research/local_llm.md", "Local LLM", "ollama context window quantization"),
    ("research/chunking.md", "Chunking", "heading overlap token budget"),
    ("research/storage.md", "Storage", "sqlite qdrant metadata catalog"),
    ("journal/garden.md", "Garden Plan", "tomato trellis compost watering"),
    ("journal/language.md", "Language Study", "vocabulary grammar flashcards"),
    ("journal/cooking_lab.md", "Cooking Lab", "experiment spice measurement"),
    ("journal/walks.md", "City Walks", "route park bench map sketch"),
]


def main() -> None:
    notes_dir = ROOT / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    for old in notes_dir.rglob("*.md"):
        old.unlink()

    manifest = {
        "dataset_id": "synthetic_v1",
        "version": "1.0.0",
        "language_mix": "en+ru",
        "description": "Depersonalized synthetic vault for offline Prometheus RAG evals.",
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    questions: list[dict[str, object]] = []
    for index, (relative, title, keywords) in enumerate(TOPICS):
        marker = f"SYNTHMARKER{index:03d}"
        path = f"notes/{relative}"
        content = f"# {title}\n\n{marker}\n"
        target = notes_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        questions.append(
            {
                "id": f"q-{index:03d}",
                "question": marker,
                "kind": "answerable",
                "expected_sources": [{"path": path}],
                "reference_keywords": [marker],
            }
        )

    # Extra answerable questions referencing Details section
    for offset in range(10):
        index = offset
        relative, title, keywords = TOPICS[index]
        path = f"notes/{relative}"
        kw = keywords.split()[0]
        questions.append(
            {
                "id": f"q-extra-{offset:03d}",
                "question": f"{marker} {kw} {title}",
                "kind": "answerable",
                "expected_sources": [{"path": path}],
                "reference_keywords": [marker],
            }
        )

    unanswerable_templates = [
        "Who is the CEO of Contoso Corporation?",
        "What is the password for the production database?",
        "When did the Mars colony launch in 2099?",
        "What is my personal phone number?",
        "Where does Alice live on Maple Street?",
        "What is the stock price of FictionalCorp tomorrow?",
        "How many users registered in the secret beta?",
        "What medical diagnosis applies to patient 404?",
        "What is the vault master key?",
        "Which private email received the invoice?",
        "What is the latitude of the hidden bunker?",
    ]
    for index, question in enumerate(unanswerable_templates):
        questions.append(
            {
                "id": f"unanswerable-{index:03d}",
                "question": question,
                "kind": "unanswerable",
                "expected_sources": [],
                "reference_keywords": [],
            }
        )

    lines = [json.dumps(item, ensure_ascii=False) for item in questions]
    (ROOT / "questions.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote dataset to {ROOT} with {len(TOPICS)} notes and {len(questions)} questions")


if __name__ == "__main__":
    main()
