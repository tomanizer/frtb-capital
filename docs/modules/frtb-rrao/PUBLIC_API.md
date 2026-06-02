# frtb-rrao public API

This document defines the stable v1 top-level import surface for
`frtb_rrao.__all__`. Symbols that are not listed here remain available from
their owning submodule only and are not part of the v1 compatibility contract.

## Stable Surface

| Category | Top-level symbols | Rationale |
| --- | --- | --- |
| Package identity | `__version__`, `PACKAGE_METADATA` | Workspace package discovery and status reporting. |
| Calculation entry point | `calculate_rrao_capital` | Primary supported RRAO run API for canonical Basel MAR23, U.S. NPR 2.0, and EU CRR3 comparison inputs. |
| Core data contracts | `RraoPosition`, `RraoBackToBackMatch`, `RraoCalculationContext`, `RraoCapitalResult`, `RraoCapitalLine`, `RraoSubtotal`, `RraoSourceLineage`, `RraoCitation`, `RraoClassificationDecision` | Public input, output, lineage, audit, and classification records. |
| Enums | `RraoClassification`, `RraoEvidenceType`, `RraoExclusionReason`, `RraoRegulatoryProfile`, `RraoInvestmentFundMethod`, `RraoInvestmentFundExposureType`, `RraoAllocationDimension` | Stable wire values used by inputs, audit payloads, adapters, and allocation reports. |
| Investment-fund data | `RraoInvestmentFundDescriptor` | Public descriptor for U.S. NPR 2.0 proposed section `__.205(e)(3)(iii)` and `__.211(a)(3)` inclusion. |
| Audit helpers | `serialize_rrao_result`, `input_hash_for_positions`, `validate_rrao_result_reconciliation` | Deterministic replay and reconciliation support for public results. |
| Batch and Arrow handoff helpers | `RRAO_HANDOFF_COLUMN_SPECS`, `RraoPositionBatch`, `RraoBatchCapitalCalculation`, `build_rrao_batch_from_columns`, `build_rrao_batch_from_positions`, `build_rrao_batch_from_handoff`, `calculate_rrao_capital_from_batch`, `input_hash_for_rrao_batch`, `normalize_rrao_arrow_table` | High-volume canonical column and Arrow handoff paths that preserve the same supported-profile capital semantics without accepted-row dataclass materialisation. |
| Allocation reports | `RraoAllocationBucket`, `RraoAllocationReport`, `SUPPORTED_RRAO_ALLOCATION_DIMENSIONS`, `build_rrao_allocation_report`, `build_rrao_allocation_reports`, `resolve_rrao_allocation_dimension`, `serialize_rrao_allocation_report`, `validate_rrao_allocation_report` | Additive line, desk, legal-entity, and evidence-type explain outputs. |
| Optional adapters | `RraoAdapterResult`, `RraoAdapterWarning`, `RraoRejectedRow`, `adapt_rrao_records`, `adapt_crif_records`, `adapt_fnet_records` | Standard-library adapters from supported CRIF/FNet-shaped rows to canonical inputs. |
| Classification/profile helpers | `classify_rrao_position`, `classify_rrao_positions`, `RraoRuleProfile`, `get_rrao_rule_profile`, `validate_rrao_positions` | Public validation, classification, and supported profile metadata. |
| Errors | `RraoInputError` | Public fail-closed input error carrying field and position context. |

## Submodule-Only Surface

The following remain intentionally submodule-only because they are implementation
or test-support details rather than stable v1 contracts:

- rule-table dataclasses and lookups in `frtb_rrao.reference_data`;
- low-level capital helpers in `frtb_rrao.capital`;
- profile-hash and profile-resolution internals in `frtb_rrao.regimes`;
- notional normalisation helpers in `frtb_rrao.validation`;
- numeric tolerance constants in `frtb_rrao.numeric`;
- low-level Arrow normalisation internals in `frtb_rrao.arrow_handoff`;
- vectorised batch implementation details in `frtb_rrao.batch`.

Tests may import these from the owning submodule when they need direct module
coverage. Downstream packages should prefer the stable surface above unless a
submodule contract is explicitly documented.

## Compatibility Control

`packages/frtb-rrao/tests/test_rrao_public_api_surface.py` pins the top-level
surface and requires fewer than 60 exported names. Changes that add top-level
exports must update this document and explain why the new symbol is a stable
v1 user contract.
