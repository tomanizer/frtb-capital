# 2026-06-12 post-consolidation simplification audit summary

Audit-only run across all eight workspace packages after the SBM, DRC, RRAO,
and CVA consolidation waves. This report records the post-consolidation state,
refreshes the code-drift baseline, and documents the remaining duplicate-group
gap for ADR 0045 Phase 6.

Guard: `make agent-guard` passed in the compliant worktree
`codex/issue-850-post-consolidation-audit`.

Skill: [`.grok/skills/frtb-simplify-audit/SKILL.md`](../../../../.grok/skills/frtb-simplify-audit/SKILL.md)

## Reports

| Package | Report | Main follow-up |
| --- | --- | --- |
| `frtb-common` | [frtb-common.md](frtb-common.md) | [#899](https://github.com/tomanizer/frtb-capital/issues/899) |
| `frtb-cva` | [frtb-cva.md](frtb-cva.md) | [#897](https://github.com/tomanizer/frtb-capital/issues/897), [#899](https://github.com/tomanizer/frtb-capital/issues/899) |
| `frtb-drc` | [frtb-drc.md](frtb-drc.md) | [#899](https://github.com/tomanizer/frtb-capital/issues/899) |
| `frtb-ima` | [frtb-ima.md](frtb-ima.md) | [#897](https://github.com/tomanizer/frtb-capital/issues/897) |
| `frtb-orchestration` | [frtb-orchestration.md](frtb-orchestration.md) | none opened |
| `frtb-result-store` | [frtb-result-store.md](frtb-result-store.md) | none opened |
| `frtb-rrao` | [frtb-rrao.md](frtb-rrao.md) | [#897](https://github.com/tomanizer/frtb-capital/issues/897), [#898](https://github.com/tomanizer/frtb-capital/issues/898), [#899](https://github.com/tomanizer/frtb-capital/issues/899) |
| `frtb-sbm` | [frtb-sbm.md](frtb-sbm.md) | [#898](https://github.com/tomanizer/frtb-capital/issues/898), [#899](https://github.com/tomanizer/frtb-capital/issues/899) |

Epic: [#725](https://github.com/tomanizer/frtb-capital/issues/725). Roadmap:
[`CONSOLIDATION_ROADMAP.md`](../../CONSOLIDATION_ROADMAP.md). Prior run:
[`2026-06-04/`](../2026-06-04/).

## Mechanical results

| Check | Result |
| --- | --- |
| `uv run python scripts/ci/check_simplification_drift.py` | passed: simplification drift audit kept |
| `uv run python scripts/ci/check_code_drift.py --json-output dist/quality/code-drift-report.json` | failed before reset: baseline stale after consolidation |
| `make drift-baseline` | refreshed `docs/quality/code_drift_baseline.json` |
| `uv run python scripts/ci/check_code_drift.py --changed --json-output dist/quality/changed-code-report.json` | passed before doc edits: 0 Python files, 0 changed functions |
| `uv run python scripts/ci/check_test_value.py --json-output dist/quality/test-value-report.json` | passed before doc edits: 0 changed test functions |
| `uv run python scripts/ci/check_dead_code.py --json-output dist/quality/dead-code-report.json` | passed before doc edits: 0 changed private definitions, 0 new runtime modules |

## Current metrics after consolidation

| Metric | 2026-06-04 baseline | 2026-06-12 scan | ADR 0045 target | Status |
| --- | ---: | ---: | ---: | --- |
| AST duplicate function groups | 36 | 37 | <= 20 | Gap documented; follow-ups #898 and #899 |
| Duplicate function instances | 61 | 65 | downward trend | Gap documented |
| Source Python LOC | 68,420 | 69,802 | report-only after reset | Baseline refreshed |
| Total Python LOC | 133,041 | 135,022 | report-only after reset | Baseline refreshed |
| Largest capital-package `batch.py` | SBM ~3013 before #846 | SBM 734, DRC 713, RRAO 698, CVA 45 | <= 800 | Met |
| Largest capital-package `arrow_batch.py` | SBM ~2302 before #846 | RRAO 383; others compatibility shims | <= 800 | Met |

The duplicate target is not met. The remaining gap is explicit rather than
hidden in the baseline: source mechanics are tracked in
[#899](https://github.com/tomanizer/frtb-capital/issues/899), oversized modules
in [#897](https://github.com/tomanizer/frtb-capital/issues/897), and test or
fixture duplicates in [#898](https://github.com/tomanizer/frtb-capital/issues/898).

## Suite-level findings

| P | Scope | Finding | Follow-up |
| --- | --- | --- | --- |
| P1 | `frtb-common` / package-local | Shared hash and batch-column mechanics still produce exact source duplicates across CVA, DRC, and RRAO. | [#899](https://github.com/tomanizer/frtb-capital/issues/899) |
| P1 | package-local | CVA and RRAO reference-data modules remain above 1000 LOC; IMA still has large NMRF, stress-period, and backtesting modules. | [#897](https://github.com/tomanizer/frtb-capital/issues/897) |
| P1 | package-local | DRC exact `_sorted_indices` duplication remains after stage split. | [#899](https://github.com/tomanizer/frtb-capital/issues/899) |
| P2 | package-local | SBM and RRAO duplicate test/fixture helpers dominate non-runtime duplicate groups. | [#898](https://github.com/tomanizer/frtb-capital/issues/898) |
| P2 | audit-only | DRC and SBM stage files are below 800 LOC but several are close to the ceiling. | Watch in future package PRs |

## Recommended implementation order

1. Burn down shared source mechanics (#899): hashing wrappers, batch text-array
   coercion, DRC sorted-index helper, and simple profile/citation helper shapes.
2. Split oversized reference/validation modules (#897): CVA and RRAO reference
   data first, then IMA NMRF/stress/backtesting.
3. Consolidate duplicate package-local test/fixture helpers (#898), preserving
   fixture hashes and fail-closed assertions.
4. Re-run `make drift-check`, `make changed-code-check`, `make test-value-check`,
   `make dead-code-check`, and `make quality-control` after each burn-down PR.

Implementation PRs remain one package per PR unless ADR 0045 or a follow-up ADR
explicitly covers a cross-package mechanics migration.
