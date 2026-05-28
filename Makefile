PYTHON_BIN ?= uv run python

# Paths to lint and typecheck. Notebooks are excluded.
LINT_PATHS := packages/*/src packages/*/tests packages/*/examples packages/*/scripts scripts
MYPY_PATHS := packages/*/src
COVERAGE_JSON := dist/coverage/frtb-ima.json

.PHONY: check lint format format-check typecheck test mutation benchmark audit-deps sbom ima sa drc cva orchestration clean

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
	mkdir -p dist/coverage
	uv run pytest packages --cov=frtb_ima --cov-report=term-missing --cov-report=json:$(COVERAGE_JSON)
	uv run python scripts/ci/check_module_coverage.py $(COVERAGE_JSON)

mutation:
	FRTB_IMA_MUTATION_IMPORT=1 HYPOTHESIS_PROFILE=dev uv run --directory packages/frtb-ima python -c "import numpy; import sys; from mutmut.__main__ import cli; sys.argv = ['mutmut', 'run']; cli()"
	uv run --directory packages/frtb-ima mutmut results

benchmark:
	uv run python scripts/benchmark_target_scale.py --output dist/benchmarks/frtb-ima-target-scale.json

audit-deps:
	uv run pip-audit

sbom:
	mkdir -p dist/sbom
	uv run cyclonedx-py environment .venv --pyproject pyproject.toml --output-reproducible --of JSON -o dist/sbom/frtb-capital.cdx.json

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
