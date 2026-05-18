.PHONY: help install fmt lint typecheck test check clean install-hooks

help:
	@echo "home-seek - common development tasks"
	@echo ""
	@echo "  make install       install runtime + dev dependencies (uv sync)"
	@echo "  make install-hooks install the pre-commit git hook"
	@echo "  make fmt           auto-format with ruff (writes changes)"
	@echo "  make lint          ruff check --fix (writes changes)"
	@echo "  make typecheck     mypy strict over src/"
	@echo "  make test          pytest"
	@echo "  make check         lint + typecheck + test (no writes)"
	@echo "  make clean         remove caches and build artifacts"

install:
	uv sync --all-groups

install-hooks:
	@mkdir -p .git/hooks
	@cp scripts/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "pre-commit hook installed at .git/hooks/pre-commit"

fmt:
	uv run ruff format src tests
	uv run ruff check --fix src tests

lint:
	uv run ruff check --fix src tests

typecheck:
	uv run mypy src

test:
	uv run pytest

check:
	uv run ruff format --check src tests
	uv run ruff check src tests
	uv run mypy src
	uv run pytest

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
