# frtb-sbm public API

This document defines the stable client integration surface for `frtb_sbm`.
Symbols listed here are top-level imports unless explicitly marked
submodule-only. Outputs are not final regulatory capital; package validation
status remains pending and supported runtime paths are limited to documented
BASEL_MAR21 slices.

## Stable surface

| Category | Symbols | Rationale |
| --- | --- | --- |
| Package identity | `PACKAGE_METADATA`, `__version__` | Workspace discovery and status reporting. |
| Row entry (Tier 3) | `calculate_sbm_capital`, `SbmSensitivity`, `SbmCalculationContext`, `SbmCapitalResult`, `SbmRiskClass`, `SbmRiskMeasure`, `SbmRegulatoryProfile`, `SbmSourceLineage` | Small books, tests, notebooks, and fixture workflows. |
| Batch entry (Tier 1) | `SbmSensitivityBatch`, `build_*_batch_from_columns`, `build_*_batch_from_arrow`, `calculate_sbm_capital_from_*_batch`, `calculate_sbm_portfolio_capital_from_batches`, `calculate_sbm_portfolio_capital_from_arrow_tables`, `input_hash_for_*_batch` | Production input table path from normalized Arrow tables to package-owned NumPy batches. |
| InputTable specs | All `*_ARROW_COLUMN_SPECS` symbols listed below | Client schema alignment and generated schema export. |
| Normalize | All `normalize_*_arrow_table` symbols listed below | Ingress from raw Arrow tables to `NormalizedArrowTable`. |
| CRIF adapter (Tier 2) | `adapt_crif_records`, `normalize_girr_delta_crif_arrow_table` from `frtb_sbm.crif` | CRIF-shaped input compatibility with explicit rejected rows. |
| Audit and replay | `serialize_sbm_result`, `input_hash_for_sensitivities`, `validate_sbm_result_reconciliation`, `to_component_summary` | Deterministic replay, reconciliation, and SA orchestration input_table. |
| Errors and support guards | `SbmInputError`, `SbmUnsupportedFeature`, `ensure_sbm_run_supported`, `ensure_sbm_risk_class_measure_supported`, `phase1_capital_supported_paths` | Fail-closed unsupported profiles and input diagnostics. |

The top-level surface is intentionally broader than RRAO because SBM exposes a
separate batch, input_table, and calculation symbol for each risk-class/measure
path. The public API surface test caps `frtb_sbm.__all__` below 340 names and
requires every documented input_table symbol to remain importable.

## Client integration

| Tier | Client input | SBM path | Notes |
| --- | --- | --- | --- |
| 1 - Arrow/Parquet input table | Tables matching one of the input table specs below | `normalize_*_arrow_table` -> `build_*_batch_from_arrow` -> `calculate_sbm_capital_from_*_batch` or portfolio dispatcher | Recommended production path. |
| 2 - CRIF/vendor rows | Iterable mapping rows or GIRR delta CRIF Arrow table | `adapt_crif_records` or `normalize_girr_delta_crif_arrow_table` | Adapter path with explicit rejected-row diagnostics. |
| 3 - Canonical dataclasses | `tuple[SbmSensitivity, ...]` plus `SbmCalculationContext` | `calculate_sbm_capital` | Small books, tests, and notebooks only. |

Supported runtime profiles: `BASEL_MAR21` for implemented delta, vega, and
curvature paths, plus `US_NPR_2_0` for GIRR delta only, as described in
[`packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md`](../../../packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md).
All other U.S. NPR 2.0 cells, and the EU CRR3 and PRA UK CRR comparison
profiles, fail closed until separately implemented and cited.

## InputTable specs and normalizers

| Path | InputTable spec | Normalizer | Builder | Capital entry |
| --- | --- | --- | --- | --- |
| GIRR delta | `GIRR_DELTA_ARROW_COLUMN_SPECS` | `normalize_girr_delta_arrow_table` | `build_girr_delta_batch_from_arrow` | `calculate_sbm_capital_from_girr_delta_batch` |
| GIRR vega | `GIRR_VEGA_ARROW_COLUMN_SPECS` | `normalize_girr_vega_arrow_table` | `build_girr_vega_batch_from_arrow` | `calculate_sbm_capital_from_girr_vega_batch` |
| GIRR curvature | `GIRR_CURVATURE_ARROW_COLUMN_SPECS` | `normalize_girr_curvature_arrow_table` | `build_girr_curvature_batch_from_arrow` | `calculate_sbm_capital_from_girr_curvature_batch` |
| FX delta | `FX_DELTA_ARROW_COLUMN_SPECS` | `normalize_fx_delta_arrow_table` | `build_fx_delta_batch_from_arrow` | `calculate_sbm_capital_from_fx_delta_batch` |
| FX vega | `FX_VEGA_ARROW_COLUMN_SPECS` | `normalize_fx_vega_arrow_table` | `build_fx_vega_batch_from_arrow` | `calculate_sbm_capital_from_fx_vega_batch` |
| FX curvature | `FX_CURVATURE_ARROW_COLUMN_SPECS` | `normalize_fx_curvature_arrow_table` | `build_fx_curvature_batch_from_arrow` | `calculate_sbm_capital_from_fx_curvature_batch` |
| Equity delta | `EQUITY_DELTA_ARROW_COLUMN_SPECS` | `normalize_equity_delta_arrow_table` | `build_equity_delta_batch_from_arrow` | `calculate_sbm_capital_from_equity_delta_batch` |
| Equity vega | `EQUITY_VEGA_ARROW_COLUMN_SPECS` | `normalize_equity_vega_arrow_table` | `build_equity_vega_batch_from_arrow` | `calculate_sbm_capital_from_equity_vega_batch` |
| Equity curvature | `EQUITY_CURVATURE_ARROW_COLUMN_SPECS` | `normalize_equity_curvature_arrow_table` | `build_equity_curvature_batch_from_arrow` | `calculate_sbm_capital_from_equity_curvature_batch` |
| Commodity delta | `COMMODITY_DELTA_ARROW_COLUMN_SPECS` | `normalize_commodity_delta_arrow_table` | `build_commodity_delta_batch_from_arrow` | `calculate_sbm_capital_from_commodity_delta_batch` |
| Commodity vega | `COMMODITY_VEGA_ARROW_COLUMN_SPECS` | `normalize_commodity_vega_arrow_table` | `build_commodity_vega_batch_from_arrow` | `calculate_sbm_capital_from_commodity_vega_batch` |
| Commodity curvature | `COMMODITY_CURVATURE_ARROW_COLUMN_SPECS` | `normalize_commodity_curvature_arrow_table` | `build_commodity_curvature_batch_from_arrow` | `calculate_sbm_capital_from_commodity_curvature_batch` |
| CSR non-sec delta | `CSR_NONSEC_DELTA_ARROW_COLUMN_SPECS` | `normalize_csr_nonsec_delta_arrow_table` | `build_csr_nonsec_delta_batch_from_arrow` | `calculate_sbm_capital_from_csr_nonsec_delta_batch` |
| CSR non-sec vega | `CSR_NONSEC_VEGA_ARROW_COLUMN_SPECS` | `normalize_csr_nonsec_vega_arrow_table` | `build_csr_nonsec_vega_batch_from_arrow` | `calculate_sbm_capital_from_csr_nonsec_vega_batch` |
| CSR non-sec curvature | `CSR_NONSEC_CURVATURE_ARROW_COLUMN_SPECS` | `normalize_csr_nonsec_curvature_arrow_table` | `build_csr_nonsec_curvature_batch_from_arrow` | `calculate_sbm_capital_from_csr_nonsec_curvature_batch` |
| CSR sec non-CTP delta | `CSR_SEC_NONCTP_DELTA_ARROW_COLUMN_SPECS` | `normalize_csr_sec_nonctp_delta_arrow_table` | `build_csr_sec_nonctp_delta_batch_from_arrow` | `calculate_sbm_capital_from_csr_sec_nonctp_delta_batch` |
| CSR sec non-CTP vega | `CSR_SEC_NONCTP_VEGA_ARROW_COLUMN_SPECS` | `normalize_csr_sec_nonctp_vega_arrow_table` | `build_csr_sec_nonctp_vega_batch_from_arrow` | `calculate_sbm_capital_from_csr_sec_nonctp_vega_batch` |
| CSR sec non-CTP curvature | `CSR_SEC_NONCTP_CURVATURE_ARROW_COLUMN_SPECS` | `normalize_csr_sec_nonctp_curvature_arrow_table` | `build_csr_sec_nonctp_curvature_batch_from_arrow` | `calculate_sbm_capital_from_csr_sec_nonctp_curvature_batch` |
| CSR sec CTP delta | `CSR_SEC_CTP_DELTA_ARROW_COLUMN_SPECS` | `normalize_csr_sec_ctp_delta_arrow_table` | `build_csr_sec_ctp_delta_batch_from_arrow` | `calculate_sbm_capital_from_csr_sec_ctp_delta_batch` |
| CSR sec CTP vega | `CSR_SEC_CTP_VEGA_ARROW_COLUMN_SPECS` | `normalize_csr_sec_ctp_vega_arrow_table` | `build_csr_sec_ctp_vega_batch_from_arrow` | `calculate_sbm_capital_from_csr_sec_ctp_vega_batch` |
| CSR sec CTP curvature | `CSR_SEC_CTP_CURVATURE_ARROW_COLUMN_SPECS` | `normalize_csr_sec_ctp_curvature_arrow_table` | `build_csr_sec_ctp_curvature_batch_from_arrow` | `calculate_sbm_capital_from_csr_sec_ctp_curvature_batch` |

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

- low-level normalization helpers inside `frtb_sbm.arrow_batch`;
- private batch sorting and coercion helpers;
- risk-class implementation modules under `frtb_sbm.risk_classes`;
- reference-data implementation details not exported from the top-level package.

Tests may import submodule helpers for coverage. Client integrations should use
the top-level symbols in this document or the suite guide
[`docs/CLIENT_INTEGRATION.md`](../../CLIENT_INTEGRATION.md).
