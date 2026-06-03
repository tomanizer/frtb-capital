# frtb-cva public API

This document defines the stable client integration surface for `frtb_cva`.
CVA is a multi-table delivery: clients provide counterparties, netting sets,
hedges, and SA-CVA sensitivities according to the selected method and profile.

Outputs are not final regulatory capital.

## Stable surface

| Category | Symbols | Rationale |
| --- | --- | --- |
| Identity | `PACKAGE_METADATA`, `__version__` | Workspace discovery and status reporting. |
| Row capital (Tier 3) | `calculate_cva_capital`, `CvaCounterparty`, `CvaNettingSet`, `CvaHedge`, `SaCvaSensitivity`, `CvaCalculationContext`, `CvaCapitalResult`, `CvaMethod`, `CvaRegulatoryProfile` | Small books, tests, notebooks, and fixture workflows. |
| Batch capital (Tier 1) | `CvaCounterpartyBatch`, `CvaNettingSetBatch`, `CvaHedgeBatch`, `SaCvaSensitivityBatch`, `calculate_cva_capital_from_batches`, `calculate_reduced_portfolio_from_batches`, `calculate_full_portfolio_from_batches`, `calculate_sa_cva_capital_from_batch`, `build_cva_counterparty_batch_from_arrow`, `build_cva_netting_set_batch_from_arrow`, `build_cva_hedge_batch_from_arrow`, `build_sa_cva_sensitivity_batch_from_arrow`, `build_*_batch_from_columns` | Production path from normalized Arrow tables to package-owned NumPy batches. |
| Handoff specs | `CVA_COUNTERPARTY_ARROW_COLUMN_SPECS`, `CVA_NETTING_SET_ARROW_COLUMN_SPECS`, `CVA_HEDGE_ARROW_COLUMN_SPECS`, `SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS` | Client schema alignment and generated schema export. |
| Normalize | `normalize_cva_counterparty_arrow_table`, `normalize_cva_netting_set_arrow_table`, `normalize_cva_hedge_arrow_table`, `normalize_sa_cva_sensitivity_arrow_table` | Ingress from raw Arrow tables to `NormalizedArrowTable`. |
| CRIF adapter (Tier 2) | `adapt_cva_records`, `CvaAdapterResult` | CRIF-shaped input compatibility where supported. |
| Scope and unsupported features | `resolve_calculation_method`, `partition_mixed_method_inputs`, `validate_method_selection`, `CvaInputError` | Fail-closed method selection and unsupported feature diagnostics. |
| Audit and impact | `serialize_cva_result`, `validate_cva_result_reconciliation`, `attribute_cva_capital`, `assess_cva_capital_impact` | Replay, reconciliation, attribution, and impact analysis. |

The high-volume batch boundary is summarized in
[`docs/performance/frtb-cva-arrow-batch-triage.md`](../../performance/frtb-cva-arrow-batch-triage.md).

## Client integration

| Tier | Client input | CVA path | Notes |
| --- | --- | --- | --- |
| 1 - Arrow/Parquet handoff | One or more tables matching the selected method | `normalize_cva_*_arrow_table` -> `build_*_batch_from_handoff` -> `calculate_cva_capital_from_batches` or SA-CVA batch calculator | Recommended production path. |
| 2 - CRIF/vendor rows | Iterable mapping rows | `adapt_cva_records` -> canonical or batch path | Adapter path with explicit diagnostics. |
| 3 - Canonical dataclasses | Counterparty, netting-set, hedge, and sensitivity dataclasses plus context | `calculate_cva_capital` | Small books, tests, and notebooks. |

Clients must supply all tables required by the selected `CvaMethod`:

| Method | Required handoffs | Optional handoffs | Unsupported/fail-closed notes |
| --- | --- | --- | --- |
| Reduced BA-CVA | Counterparty and netting-set tables | None | Materiality-threshold alternative is unsupported. |
| Full BA-CVA | Counterparty, netting-set, and hedge tables | None | Hedge eligibility metadata must be explicit. |
| SA-CVA | SA-CVA sensitivity table | Hedge identifiers when sensitivity tag is `HDG` | Unsupported SA-CVA paths fail closed; GIRR delta requires tenor and vega requires volatility input. |
| Mixed carve-out | SA-CVA sensitivity table plus BA-CVA carve-out netting-set context | Counterparty and netting-set tables for carved-out BA-CVA | Carve-out ids must match supplied netting sets. |

## Handoff column summary

The Python `ColumnSpec` tuples are the source of truth.

| Handoff | Required column families | Notes |
| --- | --- | --- |
| `CVA_COUNTERPARTY_ARROW_COLUMN_SPECS` | Counterparty id, desk, legal entity, sector, credit quality, region, source row id, lineage | Client owns counterparty mastering and sector/quality classification keys. |
| `CVA_NETTING_SET_ARROW_COLUMN_SPECS` | Netting-set id, counterparty id, EAD, maturity, discount factor, currency, sign convention, IMM flag, source row id, lineage | EAD must be non-negative after sign normalization; discount factor must be positive. |
| `CVA_HEDGE_ARROW_COLUMN_SPECS` | Hedge id, counterparty id, hedge type, notional, maturity, discount factor, reference metadata, eligibility, internal flag, lineage | Eligible hedges require `eligibility_evidence_id`; ineligible hedges require rejection evidence. |
| `SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS` | Sensitivity id, risk class, measure, tag, bucket, risk factor, amount, currency, sign convention, source row id, lineage | GIRR delta requires tenor; vega requires volatility input. Index metadata is optional but required for qualified-index remapping paths. |

## Unsupported paths

The current package fails closed for unsupported methods and features including
MAR50.9 materiality-threshold election, unsupported comparison profiles, and
unsupported SA-CVA risk-class/measure combinations. Errors are raised through
`CvaInputError` or the shared unsupported-feature error type where applicable.

## Submodule-only surface

Clients should not depend on:

- private batch validation helpers;
- low-level qualified-index remapping internals;
- reference-data implementation details not exported from the top-level package;
- internal profile warning helpers.

Tests may import submodule helpers for coverage. Client integrations should use
the top-level symbols listed here.
