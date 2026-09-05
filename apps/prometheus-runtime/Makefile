.PHONY: sync format lint typecheck arch test check

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

check: lint typecheck arch test
