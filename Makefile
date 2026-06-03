PYTHON_BIN ?= uv run python
REPO ?= tomanizer/frtb-capital
BRANCH ?= main

# Paths to lint and typecheck. Notebooks are excluded.
LINT_PATHS := packages/*/src packages/*/tests packages/*/examples packages/*/scripts scripts tests tools
MYPY_PATHS := packages/*/src
COVERAGE_JSON := dist/coverage/implemented-packages.json
COVERAGE_PACKAGES := --cov=frtb_ima --cov=frtb_rrao
MUTATION_DIST := dist/mutation

.PHONY: check ci-local ci-local-fast ci-local-full lint format format-check typecheck
.PHONY: test test-no-cov test-partial-runtime-coverage docs-check regulatory-corpus regulatory-wording
.PHONY: import-lint kernel-import-boundary adr0033-vocabulary simplification-drift import-smoke maturity-check drift-check changed-code-check test-value-check dead-code-check drift-report changed-code-report test-value-report dead-code-report drift-reports drift-baseline quality-control build
.PHONY: examples-check notebooks-check package-status-dashboard
.PHONY: release-artifacts mutation mutation-rrao mutation-score-check benchmark ima-arrow-batch-benchmark sbm-benchmark drc-benchmark rrao-benchmark cva-benchmark benchmark-suite benchmark-budget-check
.PHONY: audit-deps sbom checksums repo-controls-snapshot replay-fixture
.PHONY: validation-pack agent-setup agent-sync-main agent-new agent-guard
.PHONY: agent-worktrees agent-doctor ima sa sbm drc rrao cva orchestration clean

check: lint format-check typecheck test

ci-local: docs-check lint format-check typecheck test build

ci-local-fast: docs-check lint format-check typecheck test-no-cov

ci-local-full: ci-local audit-deps sbom examples-check notebooks-check

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
	uv run pytest packages tests $(COVERAGE_PACKAGES) --cov-report=term-missing --cov-report=json:$(COVERAGE_JSON)
	uv run python scripts/ci/check_module_coverage.py $(COVERAGE_JSON)

test-no-cov:
	uv run pytest packages

test-partial-runtime-coverage:
	mkdir -p dist/coverage
	uv run pytest packages/frtb-drc packages/frtb-cva packages/frtb-sbm \
		--cov=frtb_drc --cov=frtb_cva --cov=frtb_sbm \
		--cov-report=json:dist/coverage/partial-runtime.json
	uv run python scripts/ci/check_module_coverage.py dist/coverage/partial-runtime.json \
		--maturity partial_runtime --report-only

docs-check: regulatory-corpus regulatory-wording package-status-dashboard
	python3 scripts/ci/check_markdown_links.py
	python3 scripts/ci/check_requirement_yaml.py

regulatory-wording:
	python3 scripts/ci/check_regulatory_wording.py

package-status-dashboard:
	python3 scripts/ci/generate_package_status_dashboard.py --check

package-status-dashboard-regenerate:
	python3 scripts/ci/generate_package_status_dashboard.py

import-lint:
	uv run lint-imports

kernel-import-boundary:
	uv run python scripts/ci/check_kernel_import_boundary.py

adr0033-vocabulary:
	uv run python scripts/ci/check_adr0033_vocabulary.py

simplification-drift:
	uv run python scripts/ci/check_simplification_drift.py

import-smoke:
	uv run python scripts/ci/import_smoke.py

maturity-check:
	mkdir -p dist/quality
	uv run python scripts/ci/check_package_maturity.py --json-output dist/quality/package-maturity.json

drift-check:
	mkdir -p dist/quality
	uv run python scripts/ci/check_code_drift.py --json-output dist/quality/code-drift-report.json

changed-code-check:
	mkdir -p dist/quality
	uv run python scripts/ci/check_code_drift.py --changed --json-output dist/quality/changed-code-report.json

test-value-check:
	mkdir -p dist/quality
	uv run python scripts/ci/check_test_value.py --json-output dist/quality/test-value-report.json

dead-code-check:
	mkdir -p dist/quality
	uv run python scripts/ci/check_dead_code.py --json-output dist/quality/dead-code-report.json

drift-report:
	mkdir -p dist/quality
	uv run python scripts/ci/check_code_drift.py --json-output dist/quality/code-drift-report.json || \
		echo "warning: drift-check findings are report-only during calibration" >&2

changed-code-report:
	mkdir -p dist/quality
	uv run python scripts/ci/check_code_drift.py --changed --json-output dist/quality/changed-code-report.json || \
		echo "warning: changed-code-check findings are report-only during calibration" >&2

test-value-report:
	mkdir -p dist/quality
	uv run python scripts/ci/check_test_value.py --json-output dist/quality/test-value-report.json || \
		echo "warning: test-value-check findings are report-only during calibration" >&2

dead-code-report:
	mkdir -p dist/quality
	uv run python scripts/ci/check_dead_code.py --json-output dist/quality/dead-code-report.json || \
		echo "warning: dead-code-check findings are report-only during calibration" >&2

drift-reports: drift-report changed-code-report test-value-report dead-code-report

drift-baseline:
	uv run python scripts/ci/check_code_drift.py --update-baseline

quality-control: import-lint kernel-import-boundary adr0033-vocabulary simplification-drift import-smoke maturity-check drift-reports

regulatory-corpus:
	python3 tools/regulatory/lint_regulatory_corpus.py

build:
	rm -rf dist/release
	uv build --all-packages --out-dir dist/release

examples-check:
	uv run python packages/frtb-ima/examples/run_demo.py

notebooks-check:
	MPLBACKEND=Agg uv run --extra notebooks --directory packages/frtb-ima pytest --nbmake notebooks

mutation:
	mkdir -p $(MUTATION_DIST)/frtb-ima
	FRTB_IMA_MUTATION_IMPORT=1 HYPOTHESIS_PROFILE=dev uv run --directory packages/frtb-ima python -c "import numpy; import sys; from mutmut.__main__ import cli; sys.argv = ['mutmut', 'run']; cli()"
	uv run --directory packages/frtb-ima mutmut export-cicd-stats
	cp packages/frtb-ima/mutants/mutmut-cicd-stats.json $(MUTATION_DIST)/frtb-ima/mutmut-cicd-stats.json
	uv run --directory packages/frtb-ima mutmut results > $(MUTATION_DIST)/frtb-ima/results.txt
	cat $(MUTATION_DIST)/frtb-ima/results.txt

mutation-rrao:
	mkdir -p $(MUTATION_DIST)/frtb-rrao
	HYPOTHESIS_PROFILE=dev uv run --directory packages/frtb-rrao mutmut run
	uv run --directory packages/frtb-rrao mutmut export-cicd-stats
	cp packages/frtb-rrao/mutants/mutmut-cicd-stats.json $(MUTATION_DIST)/frtb-rrao/mutmut-cicd-stats.json
	uv run --directory packages/frtb-rrao mutmut results > $(MUTATION_DIST)/frtb-rrao/results.txt
	cat $(MUTATION_DIST)/frtb-rrao/results.txt

mutation-score-check:
	uv run python scripts/ci/check_mutation_score.py --json-output $(MUTATION_DIST)/mutation-score.json

benchmark:
	uv run python scripts/benchmark_target_scale.py --output dist/benchmarks/frtb-ima-target-scale.json

ima-arrow-batch-benchmark:
	uv run python benchmarks/ima_arrow_batch_harness.py --output dist/benchmarks/frtb-ima-arrow-batch.json

sbm-benchmark:
	uv run python benchmarks/sbm_adapter_harness.py --output dist/benchmarks/frtb-sbm-batch-arrow.json

drc-benchmark:
	uv run python benchmarks/drc_adapter_harness.py --output dist/benchmarks/frtb-drc-batch-arrow.json

rrao-benchmark:
	PYTHONPATH=packages/frtb-common/src:packages/frtb-rrao/src uv run python packages/frtb-rrao/scripts/benchmark_rrao_target_scale.py --output dist/benchmarks/frtb-rrao-target-scale.json

cva-benchmark:
	PYTHONPATH=packages/frtb-common/src:packages/frtb-cva/src uv run python packages/frtb-cva/scripts/benchmark_cva_target_scale.py --output dist/benchmarks/frtb-cva-target-scale.json

benchmark-suite: benchmark ima-arrow-batch-benchmark sbm-benchmark drc-benchmark rrao-benchmark cva-benchmark

benchmark-budget-check:
	uv run python scripts/ci/check_benchmark_budgets.py

audit-deps:
	uv run pip-audit

sbom:
	mkdir -p dist/sbom
	uv run cyclonedx-py environment .venv --pyproject pyproject.toml --output-reproducible --of JSON -o dist/sbom/frtb-capital.cdx.json

checksums: build sbom
	uv run python scripts/release_checksums.py --artifacts dist/release --sbom dist/sbom/frtb-capital.cdx.json --output dist/release/SHA256SUMS --json-output dist/release/release-checksums.json

release-artifacts: checksums

repo-controls-snapshot:
	uv run python scripts/capture_repo_controls.py --repo $(REPO) --branch $(BRANCH) --output dist/repo-controls

replay-fixture:
	mkdir -p dist/replay
	uv run python packages/frtb-ima/scripts/render_audit_report.py --output dist/replay/capital_run_v1_audit_report.md --ndjson dist/replay/capital_run_v1_desk_records.ndjson
	uv run python -m frtb_ima.replay --audit dist/replay/capital_run_v1_desk_records.ndjson --fixture packages/frtb-ima/tests/fixtures/capital_run_v1 --json-output dist/replay/capital_run_v1_replay_report.json

validation-pack:
	$(MAKE) -C packages/frtb-ima PYTHON_BIN="uv run --extra notebooks python" validation-pack

# Agent workspace helpers
AGENT ?= codex
TASK ?=

agent-setup:
	$(PYTHON_BIN) scripts/agent_worktree.py install-hooks

agent-sync-main:
	$(PYTHON_BIN) scripts/agent_worktree.py sync-main

agent-new:
	@test -n "$(TASK)" || \
		(echo "TASK is required, for example: make agent-new AGENT=codex TASK=drc-scenarios"; exit 1)
	$(PYTHON_BIN) scripts/agent_worktree.py new --agent "$(AGENT)" "$(TASK)"

agent-guard:
	$(PYTHON_BIN) scripts/agent_worktree.py guard

agent-worktrees:
	$(PYTHON_BIN) scripts/agent_worktree.py list

agent-doctor:
	$(PYTHON_BIN) scripts/agent_worktree.py doctor

# Per-package shortcuts
ima:
	uv run pytest packages/frtb-ima/tests

sa: sbm drc rrao

sbm:
	@test -d packages/frtb-sbm || (echo "frtb-sbm package not yet created"; exit 1)
	uv run pytest packages/frtb-sbm/tests

drc:
	@test -d packages/frtb-drc || (echo "frtb-drc package not yet created"; exit 1)
	uv run pytest packages/frtb-drc/tests

rrao:
	@test -d packages/frtb-rrao || (echo "frtb-rrao package not yet created"; exit 1)
	uv run pytest packages/frtb-rrao/tests

cva:
	@test -d packages/frtb-cva || (echo "frtb-cva package not yet created"; exit 1)
	uv run pytest packages/frtb-cva/tests

orchestration:
	@test -d packages/frtb-orchestration || (echo "frtb-orchestration package not yet created"; exit 1)
	uv run pytest packages/frtb-orchestration/tests

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage build dist *.egg-info
	find packages -name "__pycache__" -type d -exec rm -rf {} +
