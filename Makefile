.PHONY: install test lint format typecheck security check build run

install:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy

security:
	uv run bandit -c pyproject.toml -r src

check: lint typecheck security test

build:
	uv build

run:
	uv run finance-mcp
