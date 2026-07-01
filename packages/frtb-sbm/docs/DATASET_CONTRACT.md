# Dataset Contract

The SBM package includes committed synthetic replay fixtures under
`packages/frtb-sbm/tests/fixtures/`. These fixtures are development regression
bundles for the Standardised Approach sensitivities-based method. They are not
market data, client data, regulatory evidence, regulatory submissions, or final
regulatory capital.

The committed fixtures currently include:

- `girr_delta_v1`
- `girr_delta_us_npr_v1`
- `girr_vega_v1`
- `girr_vega_us_npr_v1`
- `girr_curvature_us_npr_v1`
- `fx_delta_us_npr_v1`
- `fx_vega_us_npr_v1`
- `fx_curvature_us_npr_v1`
- `non_girr_vega_v1`
- `fx_delta_v1`
- `equity_delta_v1`
- `commodity_delta_v1`
- `csr_nonsec_delta_v1`

Additional package tests cover Arrow batch, portfolio dispatch, curvature, CRIF,
reference data, replay, and unsupported-feature behavior. The fixture
directories above are the committed dataset replay packs.

## Boundary

The canonical fixture and runtime contract is SBM-native. It mirrors the package
objects and homogeneous batch inputs consumed by the capital layer:

- `SbmCalculationContext`
- `SbmSensitivity`
- `SbmSourceLineage`
- `SbmSensitivityBatch`
- `SbmCapitalResult`

CRIF-shaped rows are adapter inputs, not the canonical fixture schema.
`adapt_crif_records(...)` maps supported BASEL_MAR21 delta, vega, and curvature
rows into canonical `SbmSensitivity` records with explicit warnings and
rejected rows. `normalize_girr_delta_crif_arrow_table(...)` provides the
package-owned GIRR delta CRIF-to-Arrow path. Vendor-specific, SIMM-specific, or
client-specific field mappings belong in adapter documentation and tests, not
in the core replay fixture schema.

Arrow tables are the production-style high-volume handoff boundary. They are
normalised into `NormalizedArrowTable` objects and then into package-owned NumPy
`SbmSensitivityBatch` objects. Calculation kernels consume canonical
dataclasses or package-owned batches; kernels must not depend on pandas, polars,
or Arrow internals.

## Files

Each committed fixture directory contains the following files unless noted in
the fixture-local README:

- `README.md`: scenario purpose, covered regulatory paragraphs, and negative
  case intent.
- `manifest.json`: fixture identifier or schema version, profile, risk path,
  file checksums where present, row counts, and expected total capital where
  present.
- `sensitivities.json`: canonical SBM sensitivity rows and run context.
- `expected_outputs.json`: deterministic capital totals, hashes, scenario
  selections, bucket outputs, weighted sensitivities, and warnings used by
  replay tests.
- `invalid_cases.json`: negative validation and unsupported-feature cases.
- `loader.py`: fixture-local loader that converts JSON rows into package-native
  dataclasses for tests.

The fixtures are static committed artifacts. There is no package-local fixture
generation command for SBM at this time.

## Canonical Row Shape

`SbmCalculationContext` carries run-level identity and profile metadata:

- `run_id`
- `calculation_date`
- `base_currency`
- `reporting_currency`
- `profile_id`
- optional `desk_id`, `legal_entity`, `citation_policy`, and `run_controls`

`base_currency` remains run metadata. FX risk-factor currency basis is selected
only through `SbmRunControls.fx_risk_factor_basis`; the accepted value today is
`REPORTING_CURRENCY`. `BASE_CURRENCY_APPROVED` fails closed until U.S. NPR
supervisory-approval and translation-risk evidence are explicitly modeled.

`SbmSensitivity` is the canonical row shape. Required fields are:

- `sensitivity_id`
- `source_row_id`
- `desk_id`
- `legal_entity`
- `risk_class`
- `risk_measure`
- `bucket`
- `risk_factor`
- `amount`
- `amount_currency`
- `sign_convention`
- `lineage`

Optional or path-specific fields are:

- `position_id`
- `qualifier`
- `tenor`
- `option_tenor`
- `liquidity_horizon_days`
- `maturity`
- `up_shock_amount`
- `down_shock_amount`
- `mapping_citation_ids`

`SbmSourceLineage` records source-system provenance for the canonical row:

- `source_system`
- `source_file`
- `source_row_id`
- optional `source_column_map`

Every accepted row must have stable identifiers. `sensitivity_id` must be
unique within the run, and `source_row_id` must remain traceable to the upstream
input row or fixture row that created it.

## Supported Paths

The canonical risk classes are:

- `GIRR`
- `CSR_NONSEC`
- `CSR_SEC_CTP`
- `CSR_SEC_NONCTP`
- `EQUITY`
- `COMMODITY`
- `FX`

The canonical risk measures are:

- `DELTA`
- `VEGA`
- `CURVATURE`

`BASEL_MAR21` is implemented for supported delta, vega, and curvature paths
across the seven SBM risk classes. `US_NPR_2_0` is implemented only for GIRR
delta, GIRR vega, GIRR curvature, reporting-currency FX delta, vega,
curvature, equity delta, and commodity delta comparison fixtures. Unsupported
profiles or unsupported sub-features must fail closed through package errors
before any capital result is emitted.

Path-specific input requirements are enforced by validation and batch builders:

- GIRR delta, vega, and curvature rows require tenor evidence.
- Commodity and CSR delta rows require tenor evidence.
- Vega rows require `option_tenor`.
- Curvature rows require `up_shock_amount` and `down_shock_amount`.
- CSR and equity rows require a qualifier suitable for the risk class, such as
  issuer or equity name.
- Commodity rows use qualifier/location evidence where the specific path
  requires it; commodity vega does not require a qualifier.

## Arrow Handoff

The public Arrow contract is defined by the package-owned `*_ARROW_COLUMN_SPECS`
symbols in `frtb_sbm.adapters.arrow`. `frtb_sbm.arrow_batch` remains a
compatibility import path for those symbols. For each supported risk-class and
measure path, callers use:

1. `normalize_sbm_arrow_table(table, risk_class, measure, ...)`
2. `build_sbm_batch_from_arrow(handoff, risk_class, measure, ...)`
3. `calculate_sbm_capital_from_batch(batch, context=...)`

Portfolio callers can pass multiple normalised handoffs to
`calculate_sbm_portfolio_capital_from_arrow_tables(...)`. The dispatcher groups
and concatenates homogeneous `(risk_class, risk_measure)` batches before
capital aggregation so cross-row correlations are preserved.

Most Arrow input tables share these required column families:

- identity: `sensitivity_id`, `source_row_id`, `desk_id`, `legal_entity`
- classification: `risk_class`, `risk_measure`, `bucket`, `risk_factor`
- amount: `amount`, `amount_currency`, `sign_convention`
- lineage: `lineage_source_system`, `lineage_source_file`
- path axes: `tenor`, `qualifier`, `option_tenor`, `maturity`,
  `liquidity_horizon_days`, `up_shock_amount`, `down_shock_amount`, as required
  by the specific path

Normalizers preserve adapter diagnostics, source hashes, handoff hashes, and
rejected-row partitions where supplied. High-volume Arrow paths should avoid
materialising accepted `SbmSensitivity` row dataclasses.

## CRIF Adapter Inputs

CRIF is accepted as a compatibility adapter shape. `adapt_crif_records(...)`
accepts mapping rows and returns:

- accepted canonical `SbmSensitivity` rows,
- non-fatal adapter warnings,
- rejected rows with source-row snapshots and rejection reasons.

The CRIF adapter recognises supported risk-type aliases for GIRR, FX, equity,
commodity, CSR non-securitisation, CSR securitisation non-CTP, and CSR
securitisation CTP delta, vega, and curvature rows. It maps CRIF labels into
canonical SBM fields such as bucket, risk factor, qualifier, tenor, option
tenor, and curvature up/down shocks.

The GIRR delta CRIF Arrow handoff is a narrower high-volume adapter path:
`normalize_girr_delta_crif_arrow_table(...)` delegates package-neutral CRIF
column discovery and rejected-row partitioning to `frtb_common.crif`, then maps
the accepted rows into the SBM GIRR delta Arrow contract.

## Sign Conventions

Rows must carry an explicit `SbmSignConvention`:

- `PAY`
- `RECEIVE`
- `LONG`
- `SHORT`

The `amount` value must already reflect the caller's chosen sign convention.
Fixture loaders and adapters must not silently flip signs to make a capital
result match expected output.

Curvature rows use `up_shock_amount` and `down_shock_amount` for branch
selection and bucket capital. The common `amount` field remains part of the
canonical and batch schema, but curvature capital is driven by the up/down
shock fields.

## Golden Outputs

`expected_outputs.json` stores deterministic replay outputs. Tests compare
capital totals, hashes, warnings, selected scenarios, risk-class summaries,
bucket summaries, and weighted sensitivities exactly or with the tolerance used
in the package tests.

The expected outputs are regression gates for the current calculation contract.
They are not independent regulatory benchmarks.

## Regeneration Rules

When changing fixture schema, reference data semantics, weighting, aggregation,
scenario selection, unsupported-feature behavior, or audit serialization:

1. Update the affected fixture JSON and fixture-local loader.
2. Update `manifest.json` metadata and checksums where the fixture carries
   checksums.
3. Review diffs in both input files and `expected_outputs.json`.
4. Run the affected fixture tests plus the relevant adapter or batch tests.
5. Run `make agent-guard` before publishing the branch.

If only generated timestamps, row ordering, or checksums changed, treat that as
a replay-stability issue and fix the source of nondeterminism before accepting
the fixture update.
