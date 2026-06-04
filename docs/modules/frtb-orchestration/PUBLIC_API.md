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
| 3 - Manifest-routed SA inputs | `CapitalRunManifest` with supported Arrow input tables | `validate_capital_run_manifest` -> `run_standardised_approach_from_manifest` | Routes explicit tables to component-owned public adapters; file IO and client delivery-pack parsing stay outside orchestration. |

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

## Standardised Approach composition

`compose_standardised_approach_capital` accepts public
`ComponentCapitalSummary` objects from SBM, DRC, and RRAO. Those summaries are
created by each component package's `to_component_summary` adapter. The function
enforces component presence, jurisdiction-family consistency, calculation-date
consistency, base-currency consistency, and deterministic subtotal ordering.

SA is a composition label for `SBM + DRC + RRAO`; it is not a standalone
package.

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
