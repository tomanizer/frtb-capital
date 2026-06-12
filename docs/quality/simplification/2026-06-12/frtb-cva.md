# frtb-cva simplification audit

Date: 2026-06-12  
Audit-only - no runtime code changes in this report.

## Scope

`frtb-cva` owns BA-CVA and SA-CVA calculation, method/entity routing, CVA reference data, and CVA audit/impact records. It has already moved to a registry-driven entity batch surface, but reference-data and weighting modules remain the largest review hotspots.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `frtb_cva/reference_data.py` | 1146 | Oversized profile/reference table module. |
| `frtb_cva/sa_cva_reference_data.py` | 1032 | Oversized SA-CVA reference table module. |
| `frtb_cva/weighted_sensitivity.py` | 724 | Repeated vega weighting shapes remain. |
| `frtb_cva/assembly/payloads.py` | 523 | Hash/payload assembly after stage split. |

## Duplicated code

- `package-local`, P1: `_resolve_credit_quality` is duplicated between BA and SA reference modules.
- `package-local`, P1: `weighted_sensitivity.py` has exact duplicate vega weighting functions for commodity, FX, and RCS.
- `frtb-common`, P1: batch-column text/source-map helpers duplicate DRC/RRAO mechanics.
- `frtb-common`, P1: `hash_payload` shape duplicates DRC/RRAO wrappers.

## Dead or storage-only code

- Compatibility shims such as `_batch_*` and `arrow_batch.py` are intentionally small and should remain until public import compatibility is deliberately trimmed.

## `frtb-common` candidates

| Finding | Scope | Priority |
| --- | --- | --- |
| `_optional_text_array` and source-column map freezing mechanics | `frtb-common` | P1 |
| `hash_payload` wrapper over stable JSON hashing | `frtb-common` | P1 |

## Package-local factoring candidates

- Split reference tables by method/profile family under #897.
- Factor CVA vega weighting through a local strategy table; do not move risk-class weights into common.

## Over-complexity

- `project_cva_attribution`, `calculate_full_portfolio`, and `adapt_cva_records` remain large functions in the code-drift report.

## Wrappers and readability

- Entity registry dispatch is now the preferred surface; keep private compatibility shims minimal until a surface-trim PR deletes them.

## What must not move

- BA-CVA vs SA-CVA routing, hedge eligibility, credit-quality semantics, profile support, and regulatory reference values stay in `frtb-cva`.

## Recommended sequence

1. Address shared mechanics with #899.
2. Split reference-data modules under #897.
3. Factor SA-CVA vega weighting locally with exact capital parity tests.

## Validation required

- `uv run pytest packages/frtb-cva/tests`
- `make drift-check`
- `make changed-code-check`
- `make quality-control`

## Tracking

GitHub issues: [#897](https://github.com/tomanizer/frtb-capital/issues/897), [#899](https://github.com/tomanizer/frtb-capital/issues/899)
