# frtb-drc public API

This document defines the stable client integration surface for `frtb_drc`.
DRC supports three class-specific Arrow-ingest paths: non-securitisation,
securitisation non-CTP, and correlation trading portfolio (CTP). Mixed risk
classes must be split into class-specific batches before calculation; batch
entrypoints fail closed when incompatible classes are mixed.

Outputs are not final regulatory capital. U.S. NPR 2.0 content is proposed-rule
comparison material. Basel MAR22 profile support is paragraph-scoped and
documented in [PROFILE_SUPPORT_MATRIX.md](PROFILE_SUPPORT_MATRIX.md).

## Stable surface

| Category | Symbols | Rationale |
| --- | --- | --- |
| Identity | `PACKAGE_METADATA`, `__version__` | Workspace discovery and status reporting. |
| Row capital (Tier 3) | `calculate_drc_capital`, `DrcPosition`, `DrcCalculationContext`, `DrcCapitalResult`, `DrcRiskClass`, `DrcInstrumentType`, `DefaultDirection`, `DrcSeniority`, `CreditQuality`, `DrcSourceLineage` | Small books, tests, notebooks, and fixture workflows. |
| Batch capital (Tier 1) | `DrcPositionBatch`, `DrcBatchCapitalCalculation`, `build_drc_nonsec_batch_from_arrow`, `build_drc_securitisation_non_ctp_batch_from_arrow`, `build_drc_ctp_batch_from_arrow`, `build_drc_*_batch_from_columns`, `calculate_drc_capital_from_batch`, `input_hash_for_drc_batch` | Production path from normalized Arrow batches to package-owned NumPy batches. |
| Handoff specs | `DRC_NONSEC_ARROW_COLUMN_SPECS`, `DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS`, `DRC_CTP_ARROW_COLUMN_SPECS` | Client schema alignment and generated schema export. |
| Normalize | `normalize_drc_nonsec_arrow_table`, `normalize_drc_securitisation_non_ctp_arrow_table`, `normalize_drc_ctp_arrow_table` | Ingress from raw Arrow tables to `NormalizedArrowTable`. |
| Reference overlays | `DrcCalculationContext`, `DrcFxRate`, `DrcRiskWeightEvidence`, `DrcFairValueCapEvidence` | Run-scoped FX rates, securitisation risk weights, fair-value cap evidence, and offset groups. |
| Profile support | `drc_profile_support_matrix`, `DrcProfileSupportCell`, `get_rule_profile`, `ensure_risk_class_supported` | Runtime-readable support and fail-closed profile contract. |
| Audit and attribution | `validate_reconciliation`, `calculate_drc_attribution`, `validate_attribution_reconciliation`, `to_component_summary` | Replay, reconciliation, attribution, and SA orchestration handoff. |
| Impact analysis | `calculate_drc_impact`, `validate_drc_impact_reconciliation`, `DrcImpactAnalysis`, `DrcImpactRecord`, `DrcImpactMethod` | Baseline-vs-candidate change-control analysis over two reconciled DRC results. Impact records are not regulatory capital calculations and are separate from analytical Euler attribution. |
| Errors | `DrcInputError` | Public fail-closed input error carrying field context. |

Reference overlays are documented in
[`docs/CLIENT_REFERENCE_DATA.md`](../../CLIENT_REFERENCE_DATA.md). The
high-volume batch boundary is summarized in
[`docs/performance/frtb-drc-arrow-batch-triage.md`](../../performance/frtb-drc-arrow-batch-triage.md).
Column and position batch builders physically live in
`frtb_drc.adapters.positions`; `frtb_drc.batch` and the top-level `frtb_drc`
module remain stable import paths for existing callers.

## Client integration

| Tier | Client input | DRC path | Notes |
| --- | --- | --- | --- |
| 1 - Arrow/Parquet table | One class-specific table per DRC class | `normalize_drc_*_arrow_table` -> `build_drc_*_batch_from_arrow` -> `calculate_drc_capital_from_batch` | Recommended production path **per risk class**; mixed classes in one table fail closed. |
| 2 - CRIF/vendor rows | `adapt_drc_crif_rows` maps source rows to canonical positions, rejected diagnostics, or class-specific Arrow tables | `DrcCrifAdapterResult.to_arrow_tables()` -> Tier 1, or `positions` -> Tier 3 | Ingress helper only; not a capital kernel and not a source of securitisation/CTP risk-weight overlays. |
| 3 - Canonical dataclasses | `tuple[DrcPosition, ...]` plus `DrcCalculationContext` | `calculate_drc_capital` | Multi-class books in **one** result, tests, and notebooks. |

See [`packages/frtb-drc/docs/PACKAGE_JOURNEY.md`](../../../packages/frtb-drc/docs/PACKAGE_JOURNEY.md)
for row-vs-batch semantics and SA handoff when more than one DRC class is in scope.

## Impact Analysis

`calculate_drc_impact(baseline, candidate)` compares two compatible
`DrcCapitalResult` objects and returns a `DrcImpactAnalysis` containing the
suite-wide `CapitalImpact` total plus DRC branch records. The total `delta` is
always `candidate.total_drc - baseline.total_drc`; generating impact records
does not mutate either capital result or recalculate capital.

`DrcImpactRecord` labels stable bucket branches as
`DrcImpactMethod.FINITE_DIFFERENCE`. Profile changes, position bucket/category
moves, category moves, floors, zero denominators, rejected offsets, and
unsupported feature branches are labelled `UNSUPPORTED`; an explicit
`RESIDUAL` record carries any unexplained capital delta so records reconcile to
the total delta. `validate_drc_impact_reconciliation` verifies that invariant.

## Arrow Paths

| DRC class | Arrow spec | Normalizer | Builder | Context requirements |
| --- | --- | --- | --- | --- |
| Non-securitisation | `DRC_NONSEC_ARROW_COLUMN_SPECS` | `normalize_drc_nonsec_arrow_table` | `build_drc_nonsec_batch_from_arrow(..., profile_id=...)` | `DrcCalculationContext` with run id, calculation date, base currency, and profile id; builder `profile_id` must match the calculation context for non-default profiles; FX rates required for non-base-currency rows. |
| Securitisation non-CTP | `DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS` | `normalize_drc_securitisation_non_ctp_arrow_table` | `build_drc_securitisation_non_ctp_batch_from_arrow` | `US_NPR_2_0` accepts position-id keyed `securitisation_non_ctp_risk_weights` or typed evidence; `BASEL_MAR22` requires typed `DrcRiskWeightEvidence`. Fair-value cap and offset-group maps are used where supplied and profile-supported. |
| CTP | `DRC_CTP_ARROW_COLUMN_SPECS` | `normalize_drc_ctp_arrow_table` | `build_drc_ctp_batch_from_arrow` | Position-id keyed `ctp_risk_weights`, `ctp_risk_weight_evidence`, and `ctp_offset_groups` where needed for offset treatment. |

## CRIF / Vendor Ingress

`adapt_drc_crif_rows` is a package-owned adapter boundary for CRIF or
vendor-shaped default-risk rows represented as mappings. It returns
`DrcCrifAdapterResult`, whose `positions` are canonical `DrcPosition` records
and whose `rejected_rows` are deterministic `DrcRejectedCrifRow` diagnostics.
`DrcCrifDirectionStrategy` makes the source sign convention explicit:
`EXPLICIT_FIELD`, `SIGNED_NOTIONAL`, or `SIGNED_MARKET_VALUE`.

`drc_crif_result_to_arrow_tables` and
`DrcCrifAdapterResult.to_arrow_tables()` produce one `NormalizedArrowTable`
per accepted risk class. The adapter preserves source column lineage in
`DrcSourceLineage.source_column_map` and rejected-row diagnostics in the handoff
envelope. It does not import dataframe libraries and does not fill missing
securitisation or CTP risk-weight evidence.

## Arrow Column Summary

The Python `ColumnSpec` tuples are the source of truth. DRC class-specific specs
share the same canonical columns, with securitisation non-CTP and CTP relaxing
some issuer, seniority, and credit-quality requirements where the class does not
use them.

| Column family | Required | Notes |
| --- | --- | --- |
| Identity and lineage | Required | `position_id`, `source_row_id`, desk, legal entity, lineage source system, and lineage source file. |
| Class and instrument | Required | `risk_class`, `instrument_type`, `default_direction`. The Arrow table must contain only one DRC class. |
| Issuer/tranche/index keys | Class-specific | `issuer_id`, `tranche_id`, and `index_series_id` identify obligors, securitisation tranches, and index tranches. |
| Bucket and credit attributes | Class-specific | `bucket_key`, `seniority`, and `credit_quality`; securitisation and CTP risk weights are run-scoped context maps. |
| Amounts and maturity | Required | `notional`, optional `market_value`, optional `cumulative_pnl`, `maturity_years`, `currency`, and optional `lgd_override`. |
| Flags | Optional | `is_defaulted`, `is_gse`, `is_pse`, `is_covered_bond`. |
| Citations | Optional | `citation_ids` carries comma-separated regulatory citation identifiers into audit records. |

## Reference-overlay rule

Client overlays take precedence only through fields exposed on
`DrcCalculationContext`. The package validates missing and unused map entries:
mandatory position-id keyed risk weights, stale fair-value cap evidence, missing
FX rates, and unsupported decomposition evidence fail closed rather than
defaulting to zero capital.

## Submodule-only surface

Clients should not depend on:

- private batch and validation helpers in `frtb_drc.batch`;
- low-level netting helper modules;
- private identifier normalization helpers;
- internal risk-weight evidence hashing helpers.

Tests may import submodule helpers for coverage. Client integrations should use
the top-level symbols listed here.
