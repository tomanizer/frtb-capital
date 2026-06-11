# frtb-rrao public API

This document defines the stable v1 top-level import surface for
`frtb_rrao.__all__`. Symbols that are not listed here remain available from
their owning submodule only and are not part of the v1 compatibility contract.

## Stable Surface

| Category | Top-level symbols | Rationale |
| --- | --- | --- |
| Package identity | `__version__`, `PACKAGE_METADATA` | Workspace package discovery and status reporting. |
| Calculation entry point | `calculate_rrao_capital` | Primary supported RRAO run API for canonical Basel MAR23, U.S. NPR 2.0, EU CRR3 comparison, and PRA_UK_CRR inputs. |
| Core data contracts | `RraoPosition`, `RraoBackToBackMatch`, `RraoCalculationContext`, `RraoCapitalResult`, `RraoCapitalLine`, `RraoSubtotal`, `RraoSourceLineage`, `RraoCitation`, `RraoClassificationDecision` | Public input, output, lineage, audit, and classification records. |
| Enums | `RraoClassification`, `RraoEvidenceType`, `RraoExclusionReason`, `RraoRegulatoryProfile`, `RraoInvestmentFundMethod`, `RraoInvestmentFundExposureType`, `RraoAllocationDimension` | Stable wire values used by inputs, audit payloads, adapters, and allocation reports. |
| Investment-fund data | `RraoInvestmentFundDescriptor` | Public descriptor for U.S. NPR 2.0 proposed section `__.205(e)(3)(iii)` and `__.211(a)(3)` inclusion. |
| Audit helpers | `serialize_rrao_result`, `input_hash_for_positions`, `validate_rrao_result_reconciliation` | Deterministic replay and reconciliation support for public results. |
| SA orchestration handoff | `to_component_summary` | Projects `RraoCapitalResult` onto `frtb_common.ComponentCapitalSummary` for `compose_standardised_approach_capital`. |
| Batch and Arrow input_table helpers | `RRAO_ARROW_COLUMN_SPECS`, `RraoPositionBatch`, `RraoBatchCapitalCalculation`, `build_rrao_batch_from_columns`, `build_rrao_batch_from_positions`, `build_rrao_batch_from_arrow`, `calculate_rrao_capital_from_batch`, `input_hash_for_rrao_batch`, `normalize_rrao_arrow_table` | High-volume canonical column and Arrow input_table paths that preserve the same supported-profile capital semantics without accepted-row dataclass materialisation. |
| Allocation and attribution reports | `RraoAllocationBucket`, `RraoAllocationReport`, `SUPPORTED_RRAO_ALLOCATION_DIMENSIONS`, `build_rrao_allocation_report`, `build_rrao_allocation_reports`, `resolve_rrao_allocation_dimension`, `serialize_rrao_allocation_report`, `validate_rrao_allocation_report`, `calculate_rrao_attribution`, `rrao_allocation_report_to_contributions`, `build_rrao_contribution_bundle` | Additive line, desk, legal-entity, and evidence-type explain outputs plus shared `CapitalContribution` / `ComponentContributionBundle` projections using `AttributionMethod.STANDALONE`. |
| Optional adapters | `RraoAdapterResult`, `RraoAdapterWarning`, `RraoRejectedRow`, `adapt_rrao_records`, `adapt_crif_records`, `adapt_fnet_records` | Standard-library adapters from supported CRIF/FNet-shaped rows to canonical inputs. |
| Classification/profile helpers | `classify_rrao_position`, `classify_rrao_positions`, `RraoRuleProfile`, `get_rrao_rule_profile`, `validate_rrao_positions` | Public validation, classification, and supported profile metadata. |
| Errors | `RraoInputError` | Public fail-closed input error carrying field and position context. |

## Client Integration

RRAO is the template package for client-facing public API docs. The suite-level
onboarding guide is [`docs/CLIENT_INTEGRATION.md`](../../CLIENT_INTEGRATION.md),
and other package docs should copy the integration checklist in
[`docs/modules/_templates/PUBLIC_API_INTEGRATION_SECTION.md`](../_templates/PUBLIC_API_INTEGRATION_SECTION.md).

| Tier | Client input | RRAO path | Notes |
| --- | --- | --- | --- |
| 1 - Arrow/Parquet input_table | Position table matching `RRAO_ARROW_COLUMN_SPECS` | `normalize_rrao_arrow_table` -> `build_rrao_batch_from_arrow` -> `calculate_rrao_capital_from_batch` | Recommended production path. |
| 2 - CRIF/FNet/vendor rows | Iterable mapping rows | `adapt_crif_records`, `adapt_fnet_records`, or `adapt_rrao_records` | Adapter path with explicit rejected rows and diagnostics. |
| 3 - Canonical dataclasses | `tuple[RraoPosition, ...]` plus `RraoCalculationContext` | `calculate_rrao_capital` -> `build_rrao_batch_from_positions` -> `calculate_rrao_capital_from_batch` | Small books, tests, notebooks, and fixture workflows; row input is an adapter over the same batch kernel. |

The machine-readable schema artifact for this contract is
[`docs/schemas/input_table/frtb_rrao.positions.schema.json`](../../schemas/input_table/frtb_rrao.positions.schema.json),
generated from `RRAO_ARROW_COLUMN_SPECS`.

The validation harness is tracked by
[#428](https://github.com/tomanizer/frtb-capital/issues/428). Expected RRAO
usage:

```bash
uv run python scripts/validate_client_input_table.py \
  --package frtb_rrao \
  --input-table positions \
  --input path/to/rrao_positions.parquet \
  --output-dir dist/client-validation/rrao_positions/
```

### RRAO input_table column summary

The source of truth is the Python `RRAO_ARROW_COLUMN_SPECS` tuple. This table
summarizes the client-facing columns for onboarding and contract review.

| Column | Required | Logical type | Null policy | Notes |
| --- | --- | --- | --- | --- |
| `position_id` | yes | `string` | `forbid` | Aliases: `positionId` |
| `source_row_id` | yes | `string` | `forbid` | Aliases: `sourceRowId` |
| `desk_id` | yes | `string` | `forbid` | Aliases: `deskId` |
| `legal_entity` | yes | `string` | `forbid` | Aliases: `legalEntity` |
| `gross_effective_notional` | yes | `float` | `forbid` | Aliases: `grossEffectiveNotional`, `gross_notional` |
| `currency` | yes | `string` | `forbid` |  |
| `evidence_type` | yes | `string` | `forbid` | Aliases: `evidenceType` |
| `evidence_label` | yes | `string` | `forbid` | Aliases: `evidenceLabel` |
| `classification_hint` | no | `string` | `allow` | Aliases: `classificationHint` |
| `exclusion_reason` | no | `string` | `allow` | Aliases: `exclusionReason` |
| `exclusion_evidence_id` | no | `string` | `allow` | Aliases: `exclusionEvidenceId`, `exclusionEvidenceID` |
| `back_to_back_match_group_id` | no | `string` | `allow` | Aliases: `backToBackMatchGroupId`, `backToBackMatchGroupID` |
| `back_to_back_matched_position_id` | no | `string` | `allow` | Aliases: `backToBackMatchedPositionId`, `backToBackMatchedPositionID` |
| `supervisor_directive_id` | no | `string` | `allow` | Aliases: `supervisorDirectiveId`, `supervisorDirectiveID` |
| `underlying_count` | no | `integer` | `allow` | Aliases: `underlyingCount` |
| `is_path_dependent` | no | `boolean` | `allow` | Aliases: `isPathDependent` |
| `has_maturity` | no | `boolean` | `allow` | Aliases: `hasMaturity` |
| `has_strike_or_barrier` | no | `boolean` | `allow` | Aliases: `hasStrikeOrBarrier` |
| `has_multiple_strikes_or_barriers` | no | `boolean` | `allow` | Aliases: `hasMultipleStrikesOrBarriers` |
| `is_ctp_hedge` | no | `boolean` | `allow` | Aliases: `isCtpHedge` |
| `is_investment_fund_exposure` | no | `boolean` | `allow` | Aliases: `isInvestmentFundExposure` |
| `investment_fund_id` | no | `string` | `allow` | Aliases: `investmentFundId`, `fund_id`, `fundId` |
| `investment_fund_section_205_method` | no | `string` | `allow` | Aliases: `investmentFundSection205Method`, `section_205_method` |
| `investment_fund_included_exposure_type` | no | `string` | `allow` | Aliases: `investmentFundIncludedExposureType`, `included_exposure_type` |
| `investment_fund_mandate_evidence_id` | no | `string` | `allow` | Aliases: `investmentFundMandateEvidenceId`, `mandate_evidence_id` |
| `investment_fund_section_205_evidence_id` | no | `string` | `allow` | Aliases: `investmentFundSection205EvidenceId`, `section_205_evidence_id` |
| `investment_fund_gross_effective_notional` | no | `float` | `allow` | Aliases: `investmentFundGrossEffectiveNotional`, `fund_gross_effective_notional` |
| `investment_fund_included_exposure_ratio` | no | `float` | `allow` | Aliases: `investmentFundIncludedExposureRatio`, `included_exposure_ratio` |
| `investment_fund_look_through_available` | no | `boolean` | `allow` | Aliases: `investmentFundLookThroughAvailable`, `look_through_available` |
| `investment_fund_mandate_allows_rrao_exposures` | no | `boolean` | `allow` | Aliases: `investmentFundMandateAllowsRraoExposures`, `mandate_allows_rrao_exposures` |
| `notional_source` | no | `string` | `allow` | Aliases: `notionalSource` |
| `lineage_source_system` | yes | `string` | `forbid` | Aliases: `source_system`, `sourceSystem` |
| `lineage_source_file` | yes | `string` | `forbid` | Aliases: `source_file`, `sourceFile` |
| `lineage_source_row_id` | no | `string` | `allow` | Aliases: `lineageSourceRowId`, `sourceLineageRowId` |
| `citations` | no | `string` | `allow` | Comma-separated citation identifiers carried into audit records. |
| `unsupported_nested_payload` | no | `string` | `allow` | Compatibility rejection field; nested descriptors must be flattened before input_table. |

## Submodule-Only Surface

The following remain intentionally submodule-only because they are implementation
or test-support details rather than stable v1 contracts:

- rule-table dataclasses and lookups in `frtb_rrao.reference_data`;
- low-level capital helpers in `frtb_rrao.capital`;
- profile-hash and profile-resolution internals in `frtb_rrao.regimes`;
- notional normalisation helpers in `frtb_rrao.validation`;
- numeric tolerance constants in `frtb_rrao.numeric`;
- low-level Arrow normalisation internals in `frtb_rrao.arrow_batch`;
- vectorised batch implementation details in `frtb_rrao.batch`.

Tests may import these from the owning submodule when they need direct module
coverage. Downstream packages should prefer the stable surface above unless a
submodule contract is explicitly documented.

## Compatibility Control

`packages/frtb-rrao/tests/test_rrao_public_api_surface.py` pins the top-level
surface and requires fewer than 60 exported names. Changes that add top-level
exports must update this document and explain why the new symbol is a stable
v1 user contract.
