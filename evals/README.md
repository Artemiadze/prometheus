# Prometheus evals

Offline evaluation suite for retrieval and RAG quality (PRM-E16).

## Dataset layout

- `datasets/<name>/manifest.json` — dataset metadata
- `datasets/<name>/notes/**/*.md` — depersonalized markdown corpus
- `datasets/<name>/questions.jsonl` — labeled questions (answerable and unanswerable)

Regenerate `synthetic_v1` with:

```bash
python scripts/generate_synthetic_v1.py
```

## Commands

```bash
uv sync
uv run prometheus-evals retrieval --out /tmp/retrieval.json
uv run prometheus-evals rag --out /tmp/rag.json
uv run prometheus-evals perf --scale small --out /tmp/perf.json --compare-baseline
```

Profiles:

- **offline (default)** — deterministic bag-of-words embedder and extractive eval LLM (CI-safe)
- **fastembed / ollama** — reserved for manual runs when models are available locally

## Baselines

Performance baselines live in `baselines/perf_baseline.json`. Update intentionally:

```bash
uv run prometheus-evals perf --scale small --out /tmp/perf.json --update-baseline
```
