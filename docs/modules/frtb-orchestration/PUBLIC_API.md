# frtb-orchestration public API

This document defines the stable client and suite-integration surface for
`frtb_orchestration`. Orchestration composes completed component summaries; it
does not replace component-owned validation, batch builders, or calculation
kernels.

Outputs are synthetic engineering and validation evidence, not final regulatory
capital.

## Stable surface

| Category | Symbols | Rationale |
| --- | --- | --- |
| Identity | `PACKAGE_METADATA`, `__version__` | Workspace discovery and maturity reporting. |
| Suite capital | `calculate_suite_capital`, `SuiteCapitalResult`, `SuiteAttributionResult`, `SuiteAttributionReport`, `SuiteAttributionComponentReport`, `SuiteAttributionSummary`, `SuiteAttributionRecordSummary`, `SuiteAttributionGroupSummary`, `aggregate_suite_attribution`, `build_suite_attribution_report`, `summarise_suite_attribution`, `top_suite_attribution_contributors`, `suite_attribution_residual_records`, `suite_attribution_unsupported_records` | Top-of-house additive `IMA + SA + CVA` aggregation and attribution-ready branch reporting. |
| Scope capital views | `compose_scope_capital_view`, `ScopeCapitalView`, `ScopeComponentCapital`, `BindingCapitalResult`, `BindingCapitalSide`, `ScopeViewStatus` | Composes result-store-resolved scope totals into SA, IMA, CVA, output-floor binding, and dashboard-ready no-data/unsupported states. |
| Artifact evidence | `ArtifactEvidenceRef`, `ArtifactEvidenceKind`, `ArtifactEvidenceStatus`, `SuiteEvidenceComponent`, `SuiteArtifactEvidenceView`, `ComponentArtifactEvidence`, `build_suite_artifact_evidence_view` | Component-grouped read model for resolved time-series, shock, scenario-vector, and surface artifact IDs. |
| SA composition | `compose_standardised_approach_capital`, `StandardisedApproachCapitalResult`, `StandardisedComponentSubtotal`, `StandardisedFallbackRoute`, `ComponentCapitalSummary`, `StandardisedComponent` | Composes SBM, DRC, and RRAO public component summaries into Standardised Approach capital. |
| IMA handoff | `ImaCapitalSummary`, `recognise_ima_summary` | Direct or duck-typed summary handoff from IMA audit-log-shaped outputs. |
| CVA handoff | `CvaCapitalSummary`, `recognise_cva_summary` | Direct or duck-typed summary handoff from public CVA capital results. |
| Manifest routing | `CapitalRunManifest`, `ManifestInputTableRoute`, `ManifestInputTableValidation`, `ManifestValidationResult`, `SaManifestRunResult`, `validate_capital_run_manifest`, `run_standardised_approach_from_manifest` | Suite input-table routing and validation for supported Standardised Approach component tables. |
| Manifest table keys | `SBM_GIRR_DELTA_INPUT_TABLE`, `DRC_NONSEC_INPUT_TABLE`, `DRC_SECURITISATION_NON_CTP_INPUT_TABLE`, `DRC_CTP_INPUT_TABLE`, `RRAO_POSITIONS_INPUT_TABLE`, `CVA_COUNTERPARTY_INPUT_TABLE`, `CVA_NETTING_SET_INPUT_TABLE`, `CVA_HEDGE_INPUT_TABLE`, `CVA_SA_SENSITIVITY_INPUT_TABLE`, `STANDARDISED_REQUIRED_INPUT_TABLE_KEYS` | Stable logical names for manifest-supplied Arrow tables. |
| Guards and errors | `OrchestrationInputError`, `standardised_jurisdiction_family`, `suite_jurisdiction_family` | Fail-closed validation of run context, jurisdiction family, base currency, and component consistency. |

## Client integration

| Tier | Client input | Orchestration path | Notes |
| --- | --- | --- | --- |
| 1 - Completed summaries | `ImaCapitalSummary`, `StandardisedApproachCapitalResult`, and `CvaCapitalSummary` | `calculate_suite_capital` | Recommended top-of-house path once component packages have calculated capital. |
| 2 - Public component results | IMA audit-log-shaped object, public CVA result, and SBM/DRC/RRAO `ComponentCapitalSummary` outputs | `recognise_ima_summary`, `recognise_cva_summary`, `compose_standardised_approach_capital`, then `calculate_suite_capital` | Uses public result or summary contracts only. |
| 3 - Resolved hierarchy scope totals | `ScopeComponentCapital` totals for SBM, DRC, RRAO, IMA, and CVA after result-store hierarchy selection | `compose_scope_capital_view` | Result store owns hierarchy traversal; orchestration owns SA/IMA/CVA and output-floor composition. |
| 4 - Manifest-routed SA inputs | `CapitalRunManifest` with supported Arrow input tables | `validate_capital_run_manifest` -> `run_standardised_approach_from_manifest` | Routes explicit tables to component-owned public adapters; file IO and client delivery-pack parsing stay outside orchestration. |

## Suite capital

`calculate_suite_capital` accepts:

- `ima_summary`: an `ImaCapitalSummary`;
- `sa_result`: a `StandardisedApproachCapitalResult`;
- `cva_summary`: a `CvaCapitalSummary`;
- optional `run_id`.

All component inputs must share the same calculation date, base currency, and
regulatory jurisdiction family. Mixed-family inputs raise
`OrchestrationInputError`; orchestration does not emit synthetic zero-capital
fallback results for incompatible inputs.

## Suite attribution reports

The stable public import path remains `frtb_orchestration.suite` and the
package top level. Internally, suite attribution result records live under
`frtb_orchestration._suite_attribution_models`, while validation and report
assembly live under `frtb_orchestration._suite_attribution_builders`.

`aggregate_suite_attribution` is the low-level suite attribution validator. It
preserves incoming `ComponentContributionBundle` records unchanged and emits one
suite residual record.

`build_suite_attribution_report` wraps that result in a deterministic
`SuiteAttributionReport` for clients and notebooks. It supports both complete
component sets:

- top level: `frtb_ima`, `frtb_sa`, `frtb_cva`;
- decomposed SA: `frtb_ima`, `frtb_sbm`, `frtb_drc`, `frtb_rrao`, `frtb_cva`.

Partial, duplicate, or component-total-mismatched bundles raise
`OrchestrationInputError`. Report payloads include reconciliation status and
the suite residual reason, and `as_dict()` is JSON-serialisable.

`summarise_suite_attribution` consumes a `SuiteAttributionReport` and returns a
derived `SuiteAttributionSummary` containing top contributors, contributor
groups by component and source level, residual records, and unsupported
attribution records. The projection helpers expose enough drillthrough ids for
package-owned records: `component`, `contribution_id`, `source_id`,
`source_level`, `bucket_key`, `category`, `method`, `contribution`, `residual`,
`reconciliation_status`, and `reason`. These helpers do not recalculate capital
or attribution methods.

## Artifact evidence

`build_suite_artifact_evidence_view` groups already-resolved
`ArtifactEvidenceRef` records under a completed `SuiteCapitalResult`. The view
is intended for Navigator and result-store handoff layers that need to show
scenario-vector, time-series, shock, and surface provenance beside suite
capital. It preserves explicit `NO_DATA` and `UNSUPPORTED` states, and its
payload includes component-level and suite-level `status_counts` so dashboards
can render availability badges without querying artifact payloads.

Orchestration does not fetch artifact payloads, query `frtb-result-store`,
source market data, construct shock definitions, or infer surface axes. Component
packages and adapters must provide validated numeric inputs plus stable artifact
IDs/provenance; the evidence view only composes those identifiers at suite
altitude.

## Standardised Approach composition

The stable public import path remains `frtb_orchestration.standardised` and the
package top level. Internally, SA composition result records live under
`frtb_orchestration._standardised_models`, while component presence,
jurisdiction-family, run-context, fallback-route, and run-id validation live
under `frtb_orchestration._standardised_validation`.

`compose_standardised_approach_capital` accepts public
`ComponentCapitalSummary` objects from SBM, DRC, and RRAO. Those summaries are
created by each component package's `to_component_summary` adapter. The function
enforces component presence, jurisdiction-family consistency, calculation-date
consistency, base-currency consistency, and deterministic subtotal ordering.

SA is a composition label for `SBM + DRC + RRAO`; it is not a standalone
package.

## Scope capital views

`compose_scope_capital_view` accepts `ScopeComponentCapital` values for a
single hierarchy node that has already been resolved by the result store or a
future OLAP adapter. It composes:

- SA capital as `SBM + DRC + RRAO`;
- IMA and CVA totals where data exists;
- output-floor binding as `max(IMA, 0.725 * SA)`;
- total scope capital as binding market-risk capital plus CVA when binding data
  exists.

The view returns explicit `OK`, `NO_DATA`, or `UNSUPPORTED` statuses. Missing
IMA or SA inputs leave binding capital as `NO_DATA`; missing CVA remains visible
on the CVA component without fabricating successful capital. Hierarchy
metadata, parent-child traversal, and source-row lookup stay outside
orchestration.

## Manifest input tables

Manifest v1 uses explicit logical table names:

| Constant | Logical name | Owning package |
| --- | --- | --- |
| `SBM_GIRR_DELTA_INPUT_TABLE` | `sbm.girr_delta` | `frtb-sbm` |
| `DRC_NONSEC_INPUT_TABLE` | `drc.nonsec` | `frtb-drc` |
| `DRC_SECURITISATION_NON_CTP_INPUT_TABLE` | `drc.securitisation_non_ctp` | `frtb-drc` |
| `DRC_CTP_INPUT_TABLE` | `drc.ctp` | `frtb-drc` |
| `RRAO_POSITIONS_INPUT_TABLE` | `rrao.positions` | `frtb-rrao` |
| `CVA_COUNTERPARTY_INPUT_TABLE` | `cva.counterparty` | `frtb-cva` |
| `CVA_NETTING_SET_INPUT_TABLE` | `cva.netting_set` | `frtb-cva` |
| `CVA_HEDGE_INPUT_TABLE` | `cva.hedge` | `frtb-cva` |
| `CVA_SA_SENSITIVITY_INPUT_TABLE` | `cva.sa_sensitivity` | `frtb-cva` |

The component package remains the source of truth for each table schema,
normalizer, batch builder, and regulatory validation rule.

## Unsupported paths

Orchestration fails closed for missing components, mixed jurisdiction families,
mixed calculation dates, mixed base currencies, incorrect summary types, and
unsupported manifest table combinations. Unsupported and residual branch
metadata supplied by components is preserved for audit and attribution, but
orchestration does not invent exact Euler decompositions when a component marks
that method unsupported.

## Submodule-only surface

Clients should not depend on:

- private manifest routing helpers;
- private summary coercion helpers;
- package-local test fixtures that import concrete component packages;
- component package internals reached through orchestration.

Client integrations should use the top-level symbols listed here.
