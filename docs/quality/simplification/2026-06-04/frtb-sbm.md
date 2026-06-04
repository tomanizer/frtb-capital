# frtb-sbm simplification audit

Date: 2026-06-04

## Scope

Sensitivities-based method capital. Largest suite monoliths live here.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `batch.py` | 2490 | Builders, hashes, dispatch |
| `arrow_batch.py` | 1951 | Arrow conversion |
| `curvature.py` | 1897 | Curvature |
| `capital.py` | 1759 | Portfolio assembly |
| `reference_data.py` | 1599 | Reference tables |

## Duplicated code

| Finding | Scope | Priority |
| --- | --- | --- |
| ~20× `build_*_from_sensitivities` → `build_sbm_batch_from_sensitivities` | package-local | P1 |
| Many `input_hash_for_*_batch` thin wrappers | package-local | P2 |
| `_hash_payload` vs `stable_json_hash` | `frtb-common` | P1 |
| Progress: `_text`, `_citations`, `_batch_lookup` extracted | package-local | done |
| `_require_text` still in some reference-data modules | package-local | P2 |

## Dead or storage-only code

`attribution.py`, `impact.py` — explicit unsupported placeholders (keep).

## `frtb-common` candidates

Hash, Arrow conversion, optional citation de-duplication (semantics-free).

## Package-local factoring candidates

- `_batch_builders.py` — table-driven sensitivity/column builders.
- Split `batch.py` and `arrow_batch.py` by risk family or pipeline stage.
- Table-driven risk-class dispatch in `weighted_sensitivity` / `curvature` (careful with citations).

## Over-complexity

Broad risk-class branching is regulatory — simplify **mechanics**, not formulas.

## Wrappers and readability

**Highest “generated code” signal in suite:** repeated docstrings and 15-line
wrappers differing only by `SbmRiskClass` / `SbmRiskMeasure`. Replace with one
factory and thin deprecated aliases if API stability requires names.

## What must not move

Risk weights, correlations, buckets, curvature formulas, MAR21 support matrix.

## Recommended sequence

1. Factory for `build_*_from_sensitivities` (+ tests).
2. `stable_json_hash` migration.
3. Finish `_text` adoption in reference-data modules.
4. Split `batch.py` / `arrow_batch.py`.

## Validation required

Full SBM tests; hash/audit replay; `test_sbm_support_matrix.py`; `make quality-control`.

## Tracking

GitHub issue: [#544](https://github.com/tomanizer/frtb-capital/issues/544)
