# Dataset Contract

The orchestration package does not own raw market-risk datasets. It owns
suite-level routing and aggregation contracts for already-calculated or
component-owned inputs:

- IMA summaries
- Standardised Approach component summaries from SBM, DRC, and RRAO
- CVA summaries
- manifest-supplied Arrow input tables that are delegated to component-owned
  public adapters

These contracts are synthetic engineering evidence for development and
regression testing. They are not market data, client data, regulatory evidence,
regulatory submissions, or final regulatory capital.

There is no package-local fixture directory for orchestration. Package tests use
inline synthetic summaries and component-owned fixtures to prove that routing,
validation, and aggregation remain deterministic.

## Boundary

The orchestration package is a composition layer. It must not replace
component-owned schemas, validation, batch builders, or calculation kernels.

The canonical orchestration inputs are:

- `ImaCapitalSummary`
- `ComponentCapitalSummary` for SBM
- `ComponentCapitalSummary` for DRC
- `ComponentCapitalSummary` for RRAO
- `StandardisedApproachCapitalResult`
- `CvaCapitalSummary`
- `CapitalRunManifest`

The canonical orchestration outputs are:

- `ManifestValidationResult`
- `SaManifestRunResult`
- `StandardisedApproachCapitalResult`
- `SuiteCapitalResult`
- `SuiteAttributionResult`

SA is a composition label for `SBM + DRC + RRAO`. It is not a standalone package
and does not own a separate raw sensitivity, default-risk, or residual-risk
dataset.

## Summary Inputs

### IMA

`ImaCapitalSummary` is the top-of-house IMA input. It carries:

- `package_name`
- `run_id`
- `calculation_date`
- `base_currency`
- `profile_id`
- `total_ima_capital`
- `ima_eligible_desk_count`
- `sa_fallback_desk_count`
- `policy_hash`
- `input_hash`
- `citations`
- optional `warnings`

`recognise_ima_summary(...)` may project an IMA audit-log-shaped object into
this summary when the required aliases are present. IMA scenario cubes, stress
histories, NMRF artifacts, PLA vectors, and backtesting vectors remain
`frtb-ima` inputs. Orchestration consumes the summary only.

### Standardised Approach

`compose_standardised_approach_capital(...)` consumes one public
`ComponentCapitalSummary` for each SA component:

- SBM
- DRC
- RRAO

Each summary is produced by the owning component package's public
`to_component_summary` adapter. Orchestration uses the shared summary fields:

- component slot
- package name
- run id
- calculation date
- base currency
- profile id and profile hash
- input hash
- total capital
- line and subtotal counts
- excluded line count
- citations and warnings

The composed SA result preserves deterministic subtotals and optional
desk-level SA fallback routes from structural IMA eligibility evidence.

### CVA

`CvaCapitalSummary` is the top-of-house CVA input. It carries:

- `package_name`
- `run_id`
- `calculation_date`
- `base_currency`
- `profile_id`
- `method`
- `total_cva_capital`
- optional BA-CVA reduced, BA-CVA full, and SA-CVA totals
- `profile_hash`
- `input_hash`
- risk-class and counterparty counts
- `citations`
- optional `warnings`

`recognise_cva_summary(...)` projects a public CVA result into this summary.
CVA counterparty, netting-set, hedge, and SA-CVA sensitivity schemas remain
owned by `frtb-cva`.

## Manifest Input Tables

`CapitalRunManifest` is the suite-level table routing contract for supported
Standardised Approach input tables. It carries:

- `run_id`
- `calculation_date`
- `profile_id`
- `base_currency`
- `input_tables`
- optional component contexts: `sbm_context`, `drc_context`, `rrao_context`,
  and `cva_context`
- optional `reference_attachments`
- optional metadata

`input_tables` and `reference_attachments` must map non-empty logical names to
`pyarrow.Table` objects. File IO, path expansion, delivery-pack validation, and
client-specific source parsing stay outside this package.

Manifest v1 uses these public logical table names:

| Logical name | Constant | Owning package |
| --- | --- | --- |
| `sbm.girr_delta` | `SBM_GIRR_DELTA_INPUT_TABLE` | `frtb-sbm` |
| `drc.nonsec` | `DRC_NONSEC_INPUT_TABLE` | `frtb-drc` |
| `drc.securitisation_non_ctp` | `DRC_SECURITISATION_NON_CTP_INPUT_TABLE` | `frtb-drc` |
| `drc.ctp` | `DRC_CTP_INPUT_TABLE` | `frtb-drc` |
| `rrao.positions` | `RRAO_POSITIONS_INPUT_TABLE` | `frtb-rrao` |
| `cva.counterparty` | `CVA_COUNTERPARTY_INPUT_TABLE` | `frtb-cva` |
| `cva.netting_set` | `CVA_NETTING_SET_INPUT_TABLE` | `frtb-cva` |
| `cva.hedge` | `CVA_HEDGE_INPUT_TABLE` | `frtb-cva` |
| `cva.sa_sensitivity` | `CVA_SA_SENSITIVITY_INPUT_TABLE` | `frtb-cva` |

`STANDARDISED_REQUIRED_INPUT_TABLE_KEYS` currently requires:

- `sbm.girr_delta`
- `drc.nonsec`
- `rrao.positions`

The owning component package remains the source of truth for each table's
column specs, aliases, null policy, normalizer, batch builder, regulatory
validation, and sign conventions.

## Manifest Routes

`ManifestInputTableRoute` registers the public package callables for one logical
input table:

- logical table name
- optional SA component slot
- normalizer
- optional batch builder
- optional batch calculator
- optional `to_component_summary` adapter
- context attribute required for calculation routes

`validate_capital_run_manifest(...)` validates supplied tables without
calculating capital. For each known table it records:

- accepted row count
- rejected row count
- adapter diagnostics
- source table hash
- normalised input table hash

`run_standardised_approach_from_manifest(...)` validates the manifest, routes
available SA tables through the registered component callables, collects
component summaries, and composes SA capital only when the required component
set is complete. Missing routes, missing component contexts, invalid tables, or
missing required SA components fail closed and are recorded in the manifest run
result.

## Cross-Component Validation

Orchestration requires compatible run context before aggregation:

- calculation dates must match,
- base currencies must match,
- regulatory profiles must map to the same jurisdiction family,
- SA must include exactly one SBM, one DRC, and one RRAO component summary,
- suite capital must include IMA, SA, and CVA summaries of the expected public
  shapes.

Known SA families are:

- `BASEL`
- `US_NPR`
- `EU_CRR3`

The suite-level family guard also recognises supported IMA, SA, and CVA profile
strings. Mixed-family inputs raise `OrchestrationInputError`; orchestration does
not emit placeholder zero capital for incompatible inputs.

## Sign Conventions

All orchestration-level capital figures are non-negative charges in
`base_currency`:

- `total_ima_capital`
- SA component `total_capital`
- `StandardisedApproachCapitalResult.total_capital`
- `total_cva_capital`
- `SuiteCapitalResult.total_capital`

Raw sensitivity, exposure, default-risk, and residual-risk sign conventions are
component-owned. Orchestration must not flip raw input signs or reinterpret
component-specific amount fields.

## Golden Outputs

Orchestration does not commit a golden-output fixture directory. Regression
tests assert deterministic `as_dict()` payloads, stable hashes for validated
manifest input tables, exact component subtotal reconciliation, and
suite-total reconciliation:

```text
Suite total = IMA + SA + CVA
SA total = SBM + DRC + RRAO
```

The synthetic inline test data and component-owned fixtures are drift gates for
the current orchestration contract. They are not independent regulatory
benchmarks.

## Update Rules

When changing orchestration dataset, summary, manifest, or routing semantics:

1. Update the public API documentation if any stable symbol, logical table key,
   route behavior, or summary field changes.
2. Update this contract when the accepted summary shape, manifest shape, or
   validation boundary changes.
3. Update component package dataset contracts if the change affects a
   component-owned raw table schema.
4. Run orchestration tests plus affected component adapter tests.
5. Run `make agent-guard` before publishing the branch.

If a change only alters row ordering, dictionary ordering, hashes, or generated
timestamps, treat it as a determinism issue and fix the source of instability
before accepting the update.
