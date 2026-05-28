PYTHON_BIN ?= uv run python

# Paths to lint and typecheck. Notebooks are excluded.
LINT_PATHS := packages/*/src packages/*/tests packages/*/examples packages/*/scripts
MYPY_PATHS := packages/*/src

.PHONY: check lint format format-check typecheck test ima sa drc cva orchestration clean

check: lint format-check typecheck test

lint:
	uv run ruff check $(LINT_PATHS)

format:
	uv run ruff format $(LINT_PATHS)

format-check:
	uv run ruff format --check $(LINT_PATHS)

typecheck:
	uv run mypy $(MYPY_PATHS)

test:
	uv run pytest packages

# Per-package shortcuts
ima:
	uv run pytest packages/frtb-ima/tests

sa:
	@test -d packages/frtb-sa || (echo "frtb-sa package not yet created"; exit 1)
	uv run pytest packages/frtb-sa/tests

drc:
	@test -d packages/frtb-drc || (echo "frtb-drc package not yet created"; exit 1)
	uv run pytest packages/frtb-drc/tests

cva:
	@test -d packages/frtb-cva || (echo "frtb-cva package not yet created"; exit 1)
	uv run pytest packages/frtb-cva/tests

orchestration:
	@test -d packages/frtb-orchestration || (echo "frtb-orchestration package not yet created"; exit 1)
	uv run pytest packages/frtb-orchestration/tests

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage build dist *.egg-info
	find packages -name "__pycache__" -type d -exec rm -rf {} +
