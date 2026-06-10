# Agent workspace helpers
AGENT ?= codex
TASK ?= default

.PHONY: agent-ensure agent-sync-main agent-worktrees agent-guard test lint format format-check typecheck check docs-check package-maturity-check import-boundary-check kernel-dependency-check notebooks-check notebook-kernel-check examples-check quality-control drift-check drift-baseline changed-code-check test-value-check dead-code-check ci-local-full ci-local-pr ci-local-governance ci-local-performance ci-local-release benchmark-suite benchmark-budget-check sbom audit-dependencies audit-dependencies-json demo

LINT_PATHS := packages/*/src packages/*/tests packages/*/examples packages/*/scripts scripts tests tools
MYPY_PATHS := packages/frtb-common/src packages/frtb-common/tests packages/frtb-drc/src packages/frtb-drc/tests packages/frtb-ima/src packages/frtb-ima/tests packages/frtb-orchestration/src packages/frtb-orchestration/tests packages/frtb-result-store/src packages/frtb-result-store/tests packages/frtb-rrao/src packages/frtb-rrao/tests packages/frtb-sbm/src packages/frtb-sbm/tests packages/frtb-cva/src packages/frtb-cva/tests
COVERAGE_PACKAGES := --cov=frtb_common --cov=frtb_ima --cov=frtb_sbm --cov=frtb_drc --cov=frtb_rrao --cov=frtb_cva --cov=frtb_orchestration --cov=frtb_result_store
COVERAGE_JSON := dist/coverage/coverage.json

agent-ensure:
	python3 scripts/agent_worktree.py ensure --agent $(AGENT) $(TASK)

agent-sync-main:
	python3 scripts/agent_worktree.py sync-main

agent-worktrees:
	python3 scripts/agent_worktree.py list

agent-guard:
	python3 scripts/agent_worktree.py guard --agent $(AGENT)

ci-local-full: check docs-check notebooks-check examples-check package-maturity-check import-boundary-check kernel-dependency-check

ci-local-pr: test-changed package-maturity-check docs-check import-boundary-check kernel-dependency-check changed-code-check test-value-check dead-code-check

ci-local-governance: ci-local-full quality-control

ci-local-performance: test-changed benchmark-suite benchmark-budget-check quality-control

ci-local-release: ci-local-full quality-control test-partial-runtime-coverage benchmark-suite benchmark-budget-check

lint:
	uv run ruff check $(LINT_PATHS)

format:
	uv run ruff format $(LINT_PATHS)

format-check:
	uv run ruff format --diff $(LINT_PATHS)

typecheck:
	uv run mypy $(MYPY_PATHS)

test:
	mkdir -p dist/coverage
	uv run pytest packages tests $(COVERAGE_PACKAGES) --cov-report=term-missing --cov-report=json:$(COVERAGE_JSON)
	uv run python scripts/ci/check_module_coverage.py $(COVERAGE_JSON)

check: lint format-check typecheck test

test-changed:
	uv run python scripts/ci/run_changed_tests.py

docs-check:
	uv run python scripts/check_docs.py
	uv run python scripts/ci/check_release_notes.py
	uv run python scripts/ci/check_architecture_docs.py
	uv run python scripts/ci/check_documentation_ownership.py
	uv run python scripts/ci/check_openapi_snapshot.py
	uv run python scripts/ci/check_agent_instructions.py
	uv run python scripts/ci/check_profile_support_docs.py
	uv run python scripts/ci/check_package_guidance.py

package-maturity-check:
	uv run python scripts/ci/check_package_maturity.py

import-boundary-check:
	uv run lint-imports

kernel-dependency-check:
	uv run python scripts/ci/check_kernel_dependencies.py

quality-control:
	uv run python scripts/ci/quality_control.py

notebooks-check:
	uv run python scripts/ci/check_notebooks.py

notebook-kernel-check:
	uv run python scripts/ci/check_notebook_kernel_versions.py

examples-check:
	uv run python scripts/ci/check_examples.py

# Build a CycloneDX SBOM for dependency governance.
sbom:
	mkdir -p dist/sbom
	uv run cyclonedx-py environment --of JSON -o dist/sbom/frtb-capital.cdx.json

audit-dependencies:
	uv run pip-audit

audit-dependencies-json:
	mkdir -p dist/audit
	uv run pip-audit -f json -o dist/audit/pip-audit.json || true
	uv run python scripts/ci/normalize_pip_audit.py dist/audit/pip-audit.json

ci-security: sbom audit-dependencies-json

benchmark-suite:
	uv run python scripts/ci/run_benchmarks.py

benchmark-budget-check:
	uv run python scripts/ci/check_benchmark_budgets.py

drift-check:
	uv run python scripts/ci/check_code_drift.py

drift-baseline:
	uv run python scripts/ci/check_code_drift.py --update-baseline

changed-code-check:
	uv run python scripts/ci/check_changed_code.py

test-value-check:
	uv run python scripts/ci/check_test_value.py

dead-code-check:
	uv run python scripts/ci/check_dead_code.py

test-partial-runtime-coverage:
	uv run pytest tests/test_partial_runtime_coverage.py

demo:
	uv run python run_demo.py
