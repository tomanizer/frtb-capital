# frtb-rrao simplification audit

Date: 2026-06-04

## Scope

Residual risk add-on. Canonical row and batch paths; fail-closed unsupported scope.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `batch.py` | 1463 | Batch kernel |
| `reference_data.py` | 781 | Evidence rules |
| `capital.py` / `classification.py` | — | Row path |
| `arrow_batch.py` | 522 | Arrow bridge |

## Duplicated code

| Finding | Scope | Priority |
| --- | --- | --- |
| Dual kernel: dataclass vs batch validation/classification/capital | package-local | P0 |
| Improved: `_payloads`, `_result_assembly`, `_citations`, `stable_json_hash` | package-local | progress |
| Optional structural fields validated/hashed but unused in classification | audit-only | P1 |
| `accepted_row_dataclasses_materialized` always 0 | audit-only | P2 |

## Dead or storage-only code

Optional position flags (underlying_count, path_dependent, etc.) — product decision.

## `frtb-common` candidates

CRIF via `frtb_common.crif`; batch arrays at boundary.

## Package-local factoring candidates

- Shared `_validation_rules` for row + batch.
- Split `batch.py`: arrays, validation, kernel, assembly.
- DRY reference-data evidence table factories.

## Over-complexity

Maintaining two kernels is the dominant cost; unification is ADR-level if hashes change.

## Wrappers and readability

Batch column helpers in `_batch_columns` are appropriate; avoid new public aliases.

## What must not move

Evidence types, exclusions, investment-fund logic, profile weights, line semantics.

## Recommended sequence

1. Shared validation module + tests.
2. Align hashes between paths.
3. Decide structural optional fields.
4. Only then consider single kernel.

## Validation required

RRAO capital, validation, audit, Arrow, handoff, hash parity tests.

## Tracking

Consolidation: [#720](https://github.com/tomanizer/frtb-capital/issues/720) (ADR 0045 epic [#725](https://github.com/tomanizer/frtb-capital/issues/725)).
