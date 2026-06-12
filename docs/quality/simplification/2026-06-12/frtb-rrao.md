# frtb-rrao simplification audit

Date: 2026-06-12  
Audit-only - no runtime code changes in this report.

## Scope

`frtb-rrao` owns residual-risk classification, evidence validation, canonical batch calculation, allocation, attribution, and CRIF/FNet adapters. The recent consolidation wave moved row classification and row capital-line helpers onto batch kernels.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `frtb_rrao/reference_data.py` | 1033 | Oversized reference/profile module. |
| `frtb_rrao/batch.py` | 698 | Below 800 and no longer the largest suite monolith. |
| `frtb_rrao/crif.py` | 693 | Adapter hotspot. |
| `frtb_rrao/arrow_batch.py` | 383 | Below threshold. |

## Duplicated code

- `frtb-common`, P1: `_optional_text_array`, `_text_array_with_default`, source-map freezing, and `hash_payload` duplicate CVA/DRC mechanics.
- `package-local`, P2: profile fixture helpers and sample lineage builders duplicate across tests.
- `package-local`, P1: `citations_for_profile` shape duplicates CVA/SBM profile helpers.

## Dead or storage-only code

- `_payloads.py` and `_result_assembly.py` are small private compatibility paths; acceptable pending deliberate trim.

## `frtb-common` candidates

| Finding | Scope | Priority |
| --- | --- | --- |
| Batch text-array coercion mechanics | `frtb-common` | P1 |
| Hash wrapper mechanics | `frtb-common` | P1 |

## Package-local factoring candidates

- Split reference-data/profile support under #897.
- Consolidate package-local fixture helpers under #898.

## Over-complexity

- `build_rrao_batch_from_columns` and `adapt_rrao_records` remain large functions.

## Wrappers and readability

- Row public API now delegates through batch construction; keep that pattern and avoid reintroducing row-only classification logic.

## What must not move

- Residual-risk classification, back-to-back evidence, investment-fund treatment, and profile comparison behavior remain RRAO-local.

## Recommended sequence

1. Use #899 for shared mechanics.
2. Use #897 for reference-data split.
3. Use #898 for package-local test helper cleanup.

## Validation required

- `uv run pytest packages/frtb-rrao/tests`
- `make drift-check`
- `make test-value-check`
- `make quality-control`

## Tracking

GitHub issues: [#897](https://github.com/tomanizer/frtb-capital/issues/897), [#898](https://github.com/tomanizer/frtb-capital/issues/898), [#899](https://github.com/tomanizer/frtb-capital/issues/899)
