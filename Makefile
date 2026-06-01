.PHONY: install test lint format typecheck security check build run clean

install:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

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

clean:
	rm -rf .coverage .mypy_cache .pytest_cache .ruff_cache htmlcov dist build
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
