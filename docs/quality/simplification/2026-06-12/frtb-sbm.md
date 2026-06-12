# frtb-sbm simplification audit

Date: 2026-06-12  
Audit-only - no runtime code changes in this report.

## Scope

`frtb-sbm` owns SBM sensitivity ingestion, risk-class weighting, aggregation, curvature, attribution, and impact. The #846 wave removed the old wrapper matrix and split Arrow ingress, batch builders, portfolio dispatch, risk-class kernels, aggregation helpers, reference data, curvature helpers, CRIF adapters, and validation helpers into focused modules.

## Hotspot map

| Module | Lines (approx.) | Notes |
| --- | ---: | --- |
| `frtb_sbm/curvature.py` | 774 | Under 800; public curvature engine and compatibility path. |
| `frtb_sbm/adapters/arrow.py` | 742 | Arrow ingress implementation after physical split. |
| `frtb_sbm/batch.py` | 734 | Public batch compatibility/orchestration path. |
| `frtb_sbm/capital.py` | 708 | Public capital dispatcher path. |
| `frtb_sbm/attribution.py` | 684 | Attribution projection hotspot. |

## Duplicated code

- `package-local`, P2: test helper duplication remains in sample sensitivity/context/lineage builders and fixture replay tests.
- `package-local`, P2: fixture loader helpers repeat across SBM fixture packages.
- `package-local`, P2: `_coerce_risk_class` duplicates between reference profile and regimes helpers.
- `frtb-common`, P2: profile `citations_for_profile` and attribution summary status shapes overlap with other packages.

## Dead or storage-only code

- `arrow_batch.py` is a four-line compatibility import path and is intentionally retained.

## `frtb-common` candidates

| Finding | Scope | Priority |
| --- | --- | --- |
| Profile citation lookup shape | `frtb-common` | P2 |
| Attribution summary status shape | `frtb-common` | P2 |

## Package-local factoring candidates

- Move repeated test/fixture helpers into package-local test helpers under #898.
- Keep curvature and public compatibility files below 800 before adding new risk-class paths.

## Over-complexity

- Large functions remain in `capital.py`, `curvature.py`, `risk_classes/csr_sec_nonctp.py`, `risk_classes/vega.py`, and `attribution.py`, but the previous 2k-3k LOC monoliths are gone.

## Wrappers and readability

- Registry-driven public APIs are now the preferred path: `normalize_sbm_arrow_table`, `build_sbm_batch_from_arrow`, `build_sbm_batch`, `calculate_sbm_capital_from_batch`, and `input_hash_for_batch` with enum-selected paths. Do not recreate per-risk-class wrapper matrices.

## What must not move

- MAR21/MAR21-7 scenario logic, risk weights, correlations, curvature branch selection, and unsupported-profile gates remain SBM-local.

## Recommended sequence

1. Use #898 for test/fixture duplicate cleanup.
2. Use #899 for small shared mechanics only after checking profile/citation semantics.
3. Treat future SBM work as feature work, not continued #846 physical splitting.

## Validation required

- `uv run pytest packages/frtb-sbm/tests`
- `make drift-check`
- `make test-value-check`
- `make quality-control`

## Tracking

GitHub issues: [#898](https://github.com/tomanizer/frtb-capital/issues/898), [#899](https://github.com/tomanizer/frtb-capital/issues/899)
