# frtb-ima public API

This document defines the stable client integration surface for `frtb_ima`.
The package exports a large `frtb_ima.__all__`; symbols listed here are the
primary integration and audit contract. The Python `__all__` tuple remains the
machine-readable source of truth for every export name.

Outputs are prototype NPR 2.0-style engineering evidence, not final regulatory
capital.

## Stable surface

| Category | Symbols | Rationale |
| --- | --- | --- |
| Package identity | `__version__`, `PACKAGE_METADATA`, `DEFAULT_MODEL_VERSION` | Workspace discovery and status reporting. |
| Policy capital entry | `models_based_capital_for_policy`, `models_based_capital` | Primary desk/run capital assembly with regulatory policy context. |
| Run contracts | `DeskRun`, `CalculationContext`, `RegulatoryPolicy`, `RegulatoryRegime`, `CapitalRunResult`, `CapitalComponents`, `DeskCapitalResult`, `DeskEligibilityStatus` | Public run input and output shapes. |
| Scenario cube | `ScenarioCube`, `ScenarioVector`, `ScenarioPnL`, `NestedLHScenarioVectors`, `nested_lh_vectors_from_cube`, `validate_nested_lh_vectors` | NumPy-native scenario inputs for ES, LHA, and IMCC. |
| ES / IMCC / LHA | `imcc_breakdown_for_policy`, `imcc_unconstrained_breakdown`, `imcc_constrained_breakdown`, `IMCCResult`, `liquidity_horizon_adjusted_for_maturity` | Core capital components with audit decomposition. |
| NMRF / SES | `calculate_nmrf_capital_for_policy`, `NMRFValuationRunRequest`, `NMRFValuationRunResult`, `aggregate_ses_breakdown_for_policy`, `select_nmrf_method` | NMRF method selection, valuation specs, and SES aggregation. |
| RFET | `assess_rfet_evidence`, `assess_rfet_observation_batch`, `RFETEvidenceAssessment`, `RFETObservationBatch` | Modellability classification and evidence audit trail. |
| PLA | `pla_addon`, `PLAAddonResult`, `SpearmanPlaResult` | PLA diagnostics for supported regimes. |
| Audit | `CapitalRunAuditLog`, `DeskAuditRecord`, `audit_records_to_ndjson`, `render_capital_run_audit_report`, `write_capital_run_audit_report` | NDJSON audit records and deterministic Markdown reports. |
| Attribution | `desk_contributions`, `build_ima_contribution_bundle` | Read-only projection from completed `DeskAuditRecord` objects to shared `CapitalContribution` records, plus an orchestration-ready `ComponentContributionBundle(component="frtb_ima", ...)` that validates against an IMA summary total when supplied. |
| Arrow handoffs | `IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS`, `IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS`, `IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS`, `build_capital_run_input_manifest_from_arrow`, `build_rfet_observation_batch_from_arrow`, `build_scenario_metadata_batch_from_arrow` | Tabular lineage and manifest ingress through `frtb_ima.adapters.arrow`; scenario cubes remain NumPy-native. |
| Errors | `IMAIneligibleError`, `UnsupportedRegulatoryFeature`, `UnsupportedRegulatoryFeatureError` | Fail-closed desk ineligibility and unsupported regulatory paths. |

Audit record types (`CapitalRunAuditLog`, `DeskAuditRecord`) currently live in
`frtb_ima.audit`, not `frtb-common`. Promoting a suite-level audit home requires
a cross-cutting ADR.

## Client integration

| Tier | Client input | IMA path | Notes |
| --- | --- | --- | --- |
| 1 - Arrow manifest / RFET tables | Tables matching IMA Arrow column specs | `build_capital_run_input_manifest_from_arrow` and related batch builders | Tabular lineage and RFET evidence; scenario P&L remains NumPy. |
| 2 - Validated run objects | `DeskRun` plus `CalculationContext` and policy | `models_based_capital_for_policy` | Recommended production assembly path. |
| 3 - Component functions | Scenario vectors and policy slices | `imcc_breakdown_for_policy`, `pla_addon`, NMRF helpers | Tests, notebooks, and component-level validation. |

Regulatory profiles are selected through `RegulatoryPolicy` / `RegulatoryRegime`
(`FED_NPR_2_0`, `ECB_CRR3`, `PRA_UK_CRR`). Unsupported features raise
`UnsupportedRegulatoryFeatureError`.

Orchestration consumes desk-level capital and `DeskEligibilityStatus`; it does
not call internal IMA component steps directly. To feed suite attribution, pass
completed desk audit records to `build_ima_contribution_bundle(...,
total_ima_capital=ima_summary.total_ima_capital)` and give the returned bundle
to orchestration alongside SA and CVA bundles. See
[`CLIENT_DELIVERY.md`](CLIENT_DELIVERY.md) for NumPy scenario artifacts versus
Arrow tabular handoffs.

## Submodule-only surface

Clients should not depend on private `_array_utils`, `_mapping_utils`, or
`_observation_utils` modules. Observation-window validation helpers physically
live under `frtb_ima.validation.observation_windows`; `_observation_utils`
remains a compatibility path for package-local coverage tests.
Arrow ingress helpers physically live under `frtb_ima.adapters.arrow`;
`frtb_ima.arrow_batch` remains a compatibility import path.
RFET qualitative stage helpers physically live under
`frtb_ima.validation.rfet_qualitative`; `frtb_ima.rfet_evidence` remains the
compatibility import path for existing package-local tests.
RFET quantitative observation filtering physically lives under
`frtb_ima.validation.rfet_quantitative`; `frtb_ima.rfet_evidence` remains the
compatibility import path for RFET exclusion records and stage helpers.
RFET observation-window stage helpers physically live under
`frtb_ima.validation.rfet_window`; `frtb_ima.rfet_evidence` remains the
compatibility import path for existing package-local tests.
RFET required-observation threshold helpers physically live under
`frtb_ima.validation.rfet_thresholds`; `frtb_ima.rfet_evidence` remains the
compatibility import path for existing public callers.
RFET assessment result assembly physically lives under
`frtb_ima.assembly.rfet`; `frtb_ima.rfet_evidence` remains the compatibility
import path for existing public callers.
RFET columnar batch data/setup physically lives under
`frtb_ima.validation.rfet_batch`; batch assessment physically lives under
`frtb_ima.validation.rfet_batch_assessment`; `frtb_ima.rfet_evidence` remains
the compatibility import path for `assess_rfet_observation_batch`.
Backtesting exception classification helpers physically live under
`frtb_ima.validation.backtesting_stages`; `frtb_ima.backtesting` remains the
public import path for backtesting entrypoints and result records.

## References

- [`packages/frtb-ima/README.md`](../../../packages/frtb-ima/README.md)
- [`packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md`](../../../packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md)
- [`docs/CLIENT_INTEGRATION.md`](../../CLIENT_INTEGRATION.md)
