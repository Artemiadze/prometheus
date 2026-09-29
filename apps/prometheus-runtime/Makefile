.PHONY: sync format lint typecheck arch test test-domain openapi-check check

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

arch:
	uv run lint-imports

test:
	uv run pytest

test-domain:
	uv run pytest -m domain --cov=domain --cov-report=term-missing --cov-fail-under=90

openapi-check:
	@tmp=$$(mktemp); \
	trap 'rm -f $$tmp' EXIT; \
	uv run prometheus-runtime export-openapi --output $$tmp; \
	diff -u ../../contracts/openapi.yaml $$tmp

check: lint typecheck arch test openapi-check test-domain
