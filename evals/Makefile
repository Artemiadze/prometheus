.PHONY: sync format lint typecheck test check retrieval rag perf

sync:
	uv sync

format:
	uv run black src tests
	uv run ruff check --fix src tests

lint:
	uv run black --check src tests
	uv run ruff check src tests

typecheck:
	uv run mypy

test:
	uv run pytest

retrieval:
	@tmp=$$(mktemp /tmp/retrieval.XXXXXX.json); \
	uv run prometheus-evals retrieval --out $$tmp; \
	rm -f $$tmp

rag:
	@tmp=$$(mktemp /tmp/rag.XXXXXX.json); \
	uv run prometheus-evals rag --out $$tmp; \
	rm -f $$tmp

perf:
	@tmp=$$(mktemp /tmp/perf.XXXXXX.json); \
	uv run prometheus-evals perf --scale small --out $$tmp --compare-baseline; \
	rm -f $$tmp

check: lint typecheck test retrieval rag perf
