# frtb-sbm public API

This document defines the stable client integration surface for `frtb_sbm`.
Symbols listed here are top-level imports unless explicitly marked
submodule-only. Outputs are not final regulatory capital; package validation
status remains pending and supported runtime paths are limited to documented
BASEL_MAR21 slices plus the `US_NPR_2_0` GIRR delta/vega/curvature,
reporting-currency FX delta/vega/curvature, equity delta, and commodity delta
comparison slices.

## Stable surface

| Category | Symbols | Rationale |
| --- | --- | --- |
| Package identity | `PACKAGE_METADATA`, `__version__` | Workspace discovery and status reporting. |
| Row entry (Tier 3) | `calculate_sbm_capital`, `SbmSensitivity`, `SbmCalculationContext`, `SbmCapitalResult`, `SbmRiskClass`, `SbmRiskMeasure`, `SbmRegulatoryProfile`, `SbmSourceLineage` | Small books, tests, notebooks, and fixture workflows. |
| Registry | `SBM_BATCH_SPECS`, `SBM_BATCH_PATH_ORDER`, `SbmBatchSpec` | Canonical `(SbmRiskClass, SbmRiskMeasure)` routing table for supported batch paths. |
| Batch entry (Tier 1) | `SbmSensitivityBatch`, `build_sbm_batch`, `build_sbm_batch_from_arrow`, `calculate_sbm_capital_from_arrow`, `calculate_sbm_capital_from_batch`, `calculate_sbm_portfolio_capital_from_batches`, `calculate_sbm_portfolio_capital_from_arrow_tables`, `input_hash_for_batch` | Production input table path from normalized Arrow tables to package-owned NumPy batches. |
| InputTable specs | All `*_ARROW_COLUMN_SPECS` symbols listed below | Client schema alignment and generated schema export. |
| Normalize | `normalize_sbm_arrow_table` | Ingress from raw Arrow tables to `NormalizedArrowTable` using explicit `SbmRiskClass` and `SbmRiskMeasure` values. |
| CRIF adapter (Tier 2) | `adapt_crif_records`, `normalize_girr_delta_crif_arrow_table` from `frtb_sbm.crif` | CRIF-shaped input compatibility with explicit rejected rows. |
| Audit and replay | `serialize_sbm_result`, `input_hash_for_sensitivities`, `validate_sbm_result_reconciliation`, `to_component_summary` | Deterministic replay, reconciliation, and SA orchestration input_table. |
| Attribution and impact | `calculate_sbm_attribution`, `calculate_sbm_capital_impact` | Shared `CapitalContribution` Euler projection for supported delta/vega branches and finite-difference baseline-vs-candidate impact. |
| Errors and support guards | `SbmInputError`, `SbmUnsupportedFeature`, `ensure_sbm_run_supported`, `ensure_sbm_risk_class_measure_supported`, `phase1_capital_supported_paths` | Fail-closed unsupported profiles and input diagnostics. |

The registry-driven API is the client surface. Per-path Arrow normalizer,
Arrow batch builder, row/column batch builder, batch capital, and batch hash
wrappers are intentionally not exported; callers select a path with
`SbmRiskClass` and `SbmRiskMeasure`.
Arrow ingress implementation lives in `frtb_sbm.adapters.arrow`;
`frtb_sbm.arrow_batch` remains a compatibility import path for the same public
Arrow symbols.
Batch ingress builders physically live under `frtb_sbm.adapters.sensitivities`;
`frtb_sbm.batch` remains the compatibility and public import path for existing
batch callers.
Portfolio dispatch physically lives under `frtb_sbm.kernel.portfolio`;
`frtb_sbm.capital` remains the compatibility and public import path for existing
capital callers.
Shared aggregation kernels physically live under `frtb_sbm.kernel.bucket_aggregation`,
`frtb_sbm.kernel.inter_bucket_aggregation`, `frtb_sbm.kernel.risk_class_aggregation`,
`frtb_sbm.kernel.correlation_scenarios`, `frtb_sbm.kernel.pairwise_evidence`, and
`frtb_sbm.kernel.scenario_alignment`; `frtb_sbm.kernel.aggregation` and
`frtb_sbm.aggregation` remain compatibility import paths for existing aggregation callers.
GIRR delta and vega risk-class kernels physically live under
`frtb_sbm.risk_classes.girr`; `frtb_sbm.capital` remains the public dispatcher
for row and batch capital runs. GIRR weighting formulas physically live under
`frtb_sbm.risk_classes.girr_weighting`; non-GIRR vega weighting lives under
`frtb_sbm.risk_classes.vega_weighting`; non-GIRR vega correlation helpers
physically live under `frtb_sbm.risk_classes.vega_correlations`;
`frtb_sbm.risk_classes.vega` remains the public compatibility path for
vega capital and correlation callers. FX, equity, and commodity delta
weighting live under their matching `frtb_sbm.risk_classes.*_weighting`
modules; shared weighting sort and batch-axis helpers live under
`frtb_sbm.kernel.weighting`; `frtb_sbm.weighted_sensitivity`
remains the compatibility and public import path.
Input, batch, and profile hash payload assembly physically lives under
`frtb_sbm.assembly.hashes`; public callers should continue to use
`input_hash_for_sensitivities`, `input_hash_for_batch`, and profile helpers.
CRIF adapter implementation physically lives under `frtb_sbm.adapters.crif_*`;
`frtb_sbm.crif` remains the public compatibility import path.
Reference-data implementation physically lives under focused modules including
`frtb_sbm.reference_profiles`, `frtb_sbm.girr_reference_data`,
`frtb_sbm.fx_reference_data`, `frtb_sbm.vega_reference_data`,
`frtb_sbm.curvature_reference_data`, and `frtb_sbm.reference_payload`;
`frtb_sbm.reference_data` remains the compatibility and public import path.
Curvature correlation helpers physically live under
`frtb_sbm.curvature_correlations`; `frtb_sbm.curvature` remains the public
capital, branch-selection, and compatibility import path.
Curvature factor records and row-wise factor key helpers physically live under
`frtb_sbm.curvature_factors`; `frtb_sbm.curvature` remains the compatibility
path for existing curvature helper imports.
Curvature row and batch input validation physically lives under
`frtb_sbm.curvature_inputs`, `frtb_sbm.curvature_batch_inputs`, and
`frtb_sbm.curvature_batch_mapping`; `frtb_sbm.curvature` remains the public
compatibility path for existing curvature input and branch helpers.
Curvature bucket scenario evaluation, inter-bucket aggregation, and bucket
record conversion physically live under `frtb_sbm.curvature_bucket_scenarios`,
`frtb_sbm.curvature_inter_bucket_aggregation`, and
`frtb_sbm.curvature_bucket_records`; `frtb_sbm.curvature` remains the public
compatibility path for the curvature capital engine.
Validation helpers physically live under the `frtb_sbm.validation` package, including
`batch`, `batch_arrays`, `batch_lineage`, `coercion`, `context`,
`risk_class_fields`, and `sensitivity`;
`frtb_sbm.validation` remains the compatibility and public import path.
The public API surface test caps `frtb_sbm.__all__` below 400 names and requires
every documented input_table symbol to remain importable.

## Client integration

| Tier | Client input | SBM path | Notes |
| --- | --- | --- | --- |
| 1 - Arrow/Parquet input table | Tables matching one of the input table specs below | `normalize_sbm_arrow_table(..., risk_class, measure)` -> `build_sbm_batch_from_arrow(..., risk_class, measure)` -> `calculate_sbm_capital_from_batch` or portfolio dispatcher | Recommended production path. |
| 2 - CRIF/vendor rows | Iterable mapping rows or GIRR delta CRIF Arrow table | `adapt_crif_records` or `normalize_girr_delta_crif_arrow_table` | Adapter path with explicit rejected-row diagnostics. |
| 3 - Canonical dataclasses | `tuple[SbmSensitivity, ...]` plus `SbmCalculationContext` | `calculate_sbm_capital` | Small books, tests, and notebooks only. |

Supported runtime profiles: `BASEL_MAR21` for implemented delta, vega, and
curvature paths, `US_NPR_2_0` for GIRR delta/vega/curvature,
reporting-currency FX delta/vega/curvature, equity delta, and commodity delta,
and `EU_CRR3` for GIRR
delta/vega/curvature, FX delta/vega/curvature, equity delta, and commodity
delta, as described in
[`packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md`](../../../packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md).
`PRA_UK_CRR` is supported for GIRR delta only with PRA PS1/26 Appendix 1 /
PRA2026/1 citation ids. All other U.S. NPR 2.0, EU CRR3, and PRA UK CRR
comparison-profile cells fail closed until separately implemented and cited.
The PRA source map does not open additional runtime gates without exact-cell
citations, reference data, and deterministic fixtures.
ADR 0048 records the maturity standard: runtime gates open only with
profile-owned citation metadata and deterministic evidence for the exact cell,
or an ADR-approved shared-fixture rationale.

Attribution is supported after a capital run through
`calculate_sbm_attribution(result)`. Delta and vega records use analytical Euler
where the selected scenario retained complete pairwise correlation evidence and
no active floor or alternative `S_b` branch is present. Curvature, active floors,
alternative `S_b`, missing scenario detail, and incomplete pairwise evidence are
reported as explicit unsupported residual records. `calculate_sbm_capital_impact`
compares two capital results by finite difference and must not be interpreted as
a marginal contribution.

## InputTable specs

Use each spec with `normalize_sbm_arrow_table(table, risk_class, measure)`,
`build_sbm_batch_from_arrow(handoff, risk_class, measure)`, and
`calculate_sbm_capital_from_batch(batch, context=...)` or
`calculate_sbm_capital_from_arrow(handoff, risk_class, measure, context=...)`.

| Path | InputTable spec | Registry path |
| --- | --- | --- |
| GIRR delta | `GIRR_DELTA_ARROW_COLUMN_SPECS` | `SbmRiskClass.GIRR`, `SbmRiskMeasure.DELTA` |
| GIRR vega | `GIRR_VEGA_ARROW_COLUMN_SPECS` | `SbmRiskClass.GIRR`, `SbmRiskMeasure.VEGA` |
| GIRR curvature | `GIRR_CURVATURE_ARROW_COLUMN_SPECS` | `SbmRiskClass.GIRR`, `SbmRiskMeasure.CURVATURE` |
| FX delta | `FX_DELTA_ARROW_COLUMN_SPECS` | `SbmRiskClass.FX`, `SbmRiskMeasure.DELTA` |
| FX vega | `FX_VEGA_ARROW_COLUMN_SPECS` | `SbmRiskClass.FX`, `SbmRiskMeasure.VEGA` |
| FX curvature | `FX_CURVATURE_ARROW_COLUMN_SPECS` | `SbmRiskClass.FX`, `SbmRiskMeasure.CURVATURE` |
| Equity delta | `EQUITY_DELTA_ARROW_COLUMN_SPECS` | `SbmRiskClass.EQUITY`, `SbmRiskMeasure.DELTA` |
| Equity vega | `EQUITY_VEGA_ARROW_COLUMN_SPECS` | `SbmRiskClass.EQUITY`, `SbmRiskMeasure.VEGA` |
| Equity curvature | `EQUITY_CURVATURE_ARROW_COLUMN_SPECS` | `SbmRiskClass.EQUITY`, `SbmRiskMeasure.CURVATURE` |
| Commodity delta | `COMMODITY_DELTA_ARROW_COLUMN_SPECS` | `SbmRiskClass.COMMODITY`, `SbmRiskMeasure.DELTA` |
| Commodity vega | `COMMODITY_VEGA_ARROW_COLUMN_SPECS` | `SbmRiskClass.COMMODITY`, `SbmRiskMeasure.VEGA` |
| Commodity curvature | `COMMODITY_CURVATURE_ARROW_COLUMN_SPECS` | `SbmRiskClass.COMMODITY`, `SbmRiskMeasure.CURVATURE` |
| CSR non-sec delta | `CSR_NONSEC_DELTA_ARROW_COLUMN_SPECS` | `SbmRiskClass.CSR_NONSEC`, `SbmRiskMeasure.DELTA` |
| CSR non-sec vega | `CSR_NONSEC_VEGA_ARROW_COLUMN_SPECS` | `SbmRiskClass.CSR_NONSEC`, `SbmRiskMeasure.VEGA` |
| CSR non-sec curvature | `CSR_NONSEC_CURVATURE_ARROW_COLUMN_SPECS` | `SbmRiskClass.CSR_NONSEC`, `SbmRiskMeasure.CURVATURE` |
| CSR sec non-CTP delta | `CSR_SEC_NONCTP_DELTA_ARROW_COLUMN_SPECS` | `SbmRiskClass.CSR_SEC_NONCTP`, `SbmRiskMeasure.DELTA` |
| CSR sec non-CTP vega | `CSR_SEC_NONCTP_VEGA_ARROW_COLUMN_SPECS` | `SbmRiskClass.CSR_SEC_NONCTP`, `SbmRiskMeasure.VEGA` |
| CSR sec non-CTP curvature | `CSR_SEC_NONCTP_CURVATURE_ARROW_COLUMN_SPECS` | `SbmRiskClass.CSR_SEC_NONCTP`, `SbmRiskMeasure.CURVATURE` |
| CSR sec CTP delta | `CSR_SEC_CTP_DELTA_ARROW_COLUMN_SPECS` | `SbmRiskClass.CSR_SEC_CTP`, `SbmRiskMeasure.DELTA` |
| CSR sec CTP vega | `CSR_SEC_CTP_VEGA_ARROW_COLUMN_SPECS` | `SbmRiskClass.CSR_SEC_CTP`, `SbmRiskMeasure.VEGA` |
| CSR sec CTP curvature | `CSR_SEC_CTP_CURVATURE_ARROW_COLUMN_SPECS` | `SbmRiskClass.CSR_SEC_CTP`, `SbmRiskMeasure.CURVATURE` |

Curvature input_tables are capital-producing for supported BASEL_MAR21 rows. The
GIRR curvature input_table also supports validation and batch construction for
client feed testing. Unsupported curvature sub-features, including equity repo
curvature where not implemented, fail closed.

## InputTable column summary

The Python `ColumnSpec` tuples are the source of truth. Most SBM input_tables share
these axes:

| Column family | Required | Notes |
| --- | --- | --- |
| Identity | Required | `sensitivity_id`, `source_row_id`, desk, legal entity. |
| Classification | Required | `risk_class`, `risk_measure`, bucket, qualifier, risk factor, and risk-class-specific issuer or curve keys. |
| Amount | Required | Sensitivity or curvature amount with client-side sign convention already applied. |
| Axis fields | Path-specific | Tenor, option tenor, maturity, up/down curvature branch values, and mapping citation ids as required by the path. |
| Lineage | Required for audit-ready runs | Source system, file, row id, and citation identifiers where supported. |

Generated JSON schemas from these specs are tracked by
[#423](https://github.com/tomanizer/frtb-capital/issues/423).

## Submodule-only surface

Clients should not depend on:

- low-level normalization helpers inside `frtb_sbm.adapters.arrow`;
- private batch sorting and coercion helpers;
- risk-class implementation modules under `frtb_sbm.risk_classes`;
- reference-data implementation details not exported from the top-level package.

Tests may import submodule helpers for coverage. Client integrations should use
the top-level symbols in this document or the suite guide
[`docs/CLIENT_INTEGRATION.md`](../../CLIENT_INTEGRATION.md).
