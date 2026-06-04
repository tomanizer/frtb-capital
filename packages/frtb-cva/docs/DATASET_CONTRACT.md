# Dataset Contract

The CVA package includes committed synthetic fixture packs under
`packages/frtb-cva/tests/fixtures/`. They are regression fixtures for
development, not market data, client data, regulatory evidence, or a regulatory
reporting submission.

The committed fixture packs are:

- `ba_cva_reduced_v1/`: reduced BA-CVA cases for the delivered Basel MAR50
  slice.
- `sa_cva_girr_delta_v1/`: SA-CVA GIRR delta cases, hedge-offset cases, and
  invalid-input cases for validation gates.
- `handoff/`: minimal Parquet tables for the package Arrow handoff path.

The JSON fixture packs are static checked-in inputs. Unlike the IMA fixture
pack, CVA does not currently have a package-local fixture generator command.
When changing fixture schema or expected calculation semantics, update the
fixture JSON and loader code directly, then review the complete diff and run
the CVA checks listed below.

## Boundary

The canonical CVA fixture shape is CVA-native. It mirrors the package inputs
that the capital layer already consumes:

- `CvaCalculationContext`
- `CvaCounterparty`
- `CvaNettingSet`
- `CvaHedge`
- `SaCvaSensitivity`

CRIF/vendor-shaped rows are adapter inputs, not the canonical regression
fixture schema. Vendor field mappings belong in adapter documentation and tests;
core fixtures should continue to use CVA-native records and enum values so that
BA-CVA, SA-CVA, mixed carve-out, audit, and batch paths all exercise the same
domain contract.

## Files

`packages/frtb-cva/tests/fixtures/ba_cva_reduced_v1/` contains:

- `manifest.json`: fixture id, schema version, Basel profile, selected method,
  and covered case ids.
- `inputs.json`: run context, valid counterparty/netting-set cases, and
  invalid validation cases.
- `loader.py`: fixture loader that converts JSON rows into frozen CVA
  dataclasses for tests.
- `README.md`: case-level regulatory intent and citation ids.

`packages/frtb-cva/tests/fixtures/sa_cva_girr_delta_v1/` contains:

- `manifest.json`: fixture id, schema version, Basel profile, selected method,
  valid case ids, and invalid case ids.
- `inputs.json`: SA-CVA context, sensitivity rows, hedge rows, and invalid
  validation cases.
- `expected_outputs.json`: golden scalar outputs for selected SA-CVA GIRR delta
  cases.
- `loader.py`: fixture loader that converts JSON rows into frozen CVA
  dataclasses for tests.
- `README.md`: case-level regulatory intent, sign convention, and citation ids.

`packages/frtb-cva/tests/fixtures/handoff/` contains minimal Parquet examples
for the four public Arrow table families:

- `cva_counterparty_minimal.parquet`
- `cva_netting_set_minimal.parquet`
- `cva_hedge_minimal.parquet`
- `sa_cva_sensitivity_minimal.parquet`

## Production Input Lineage

Production-style CVA runs should carry stable source lineage on every accepted
record. The canonical dataclasses expose `CvaSourceLineage` with:

- source system,
- source file,
- source row id,
- optional source-column map.

The Arrow handoff path carries the same lineage through `lineage_source_system`,
`lineage_source_file`, and optional `lineage_source_row_id` columns. Batch
builders preserve `source_hash`, `handoff_hash`, and adapter diagnostics so
audit output and replay can distinguish source content, normalized table
content, and package-owned calculation inputs.

## Arrow Table Handoff

High-volume tabular inputs should enter through these public normalizers and
batch builders:

| Input family | Normalize | Build batch |
| --- | --- | --- |
| Counterparties | `normalize_cva_counterparty_arrow_table(...)` | `build_cva_counterparty_batch_from_arrow(...)` |
| Netting sets | `normalize_cva_netting_set_arrow_table(...)` | `build_cva_netting_set_batch_from_arrow(...)` |
| Hedges | `normalize_cva_hedge_arrow_table(...)` | `build_cva_hedge_batch_from_arrow(...)` |
| SA-CVA sensitivities | `normalize_sa_cva_sensitivity_arrow_table(...)` | `build_sa_cva_sensitivity_batch_from_arrow(...)` |

The Python `ColumnSpec` tuples are the source of truth:

- `CVA_COUNTERPARTY_ARROW_COLUMN_SPECS`
- `CVA_NETTING_SET_ARROW_COLUMN_SPECS`
- `CVA_HEDGE_ARROW_COLUMN_SPECS`
- `SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS`

These specs accept documented aliases, normalize to canonical snake_case names,
and enforce required columns, null policy, and logical type before NumPy batch
construction. Calculation kernels consume package-owned batches, not
`pyarrow.Table` objects.

### Required Column Families

Counterparty tables carry:

- counterparty id,
- desk id,
- legal entity,
- sector,
- credit quality,
- region,
- source row id,
- lineage source system and file,
- optional lineage source row id.

Netting-set tables carry:

- netting-set id,
- counterparty id,
- exposure at default,
- effective maturity,
- discount factor,
- currency,
- sign convention,
- IMM EAD flag,
- source row id,
- optional BA-CVA carve-out flag,
- optional explicit-discount-factor flag,
- lineage source system and file,
- optional lineage source row id.

Hedge tables carry:

- hedge id,
- source row id,
- counterparty id,
- hedge type,
- notional,
- remaining maturity,
- discount factor,
- reference sector, reference credit quality, reference region, and reference relation,
- eligibility,
- internal-hedge flag,
- optional explicit-discount-factor flag,
- optional internal desk counterparty id,
- optional SA-CVA risk class,
- optional eligibility evidence id,
- optional rejection reason,
- lineage source system and file,
- optional lineage source row id.

SA-CVA sensitivity tables carry:

- sensitivity id,
- risk class,
- risk measure,
- CVA/hedge sensitivity tag,
- bucket id,
- risk-factor key,
- amount,
- amount currency,
- sign convention,
- source row id,
- optional tenor,
- optional volatility input,
- optional hedge id,
- optional qualified-index metadata,
- lineage source system and file,
- optional lineage source row id.

## Sign Conventions

Fixture and Arrow inputs must use explicit `sign_convention` values. The
current fixtures use:

- `non_negative` for BA-CVA exposure-at-default rows.
- `positive_loss` for SA-CVA sensitivities.

Do not flip signs inside fixture loaders or batch builders to make a test pass.
If a vendor feed uses a different sign convention, normalize it in an adapter
and keep the normalized CVA-native fixture/batch contract explicit.

## Golden Outputs

`sa_cva_girr_delta_v1/expected_outputs.json` stores selected scalar outputs for
SA-CVA GIRR delta fixture cases. Tests compare those values with deterministic
floating-point tolerances and compare categorical validation outcomes exactly.

Reduced BA-CVA fixture tests primarily compare row, batch, and Arrow paths for
the same synthetic inputs. They are drift gates for the current calculation
contract, not independent regulatory benchmarks.

## Regeneration Rules

When changing fixture schema or calculation semantics:

1. Update the relevant fixture `inputs.json`, `manifest.json`, README, loader,
   and expected-output file.
2. Review diffs in both inputs and expected outputs.
3. Run the affected CVA tests, for example:

```bash
uv run pytest packages/frtb-cva/tests/test_cva_ba_cva_fixture_workflow.py \
  packages/frtb-cva/tests/test_cva_sa_cva_fixture_workflow.py \
  packages/frtb-cva/tests/test_cva_arrow_batch.py
```

4. For broader CVA changes, run:

```bash
uv run pytest packages/frtb-cva/tests
```

5. Before publishing package documentation changes, run `make quality-control`
   from the repository root when practical.

If only generated timestamps or incidental ordering changed, fix the fixture or
loader determinism before accepting the update.
