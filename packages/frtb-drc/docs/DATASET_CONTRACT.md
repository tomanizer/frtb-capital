# Dataset Contract

The DRC package includes committed synthetic fixture packs under
`packages/frtb-drc/tests/fixtures/`. They are regression fixtures for
development, not market data, client data, regulatory evidence, or a regulatory
reporting submission.

The committed fixture packs are:

- `drc_nonsec_v1/`: static U.S. NPR 2.0 non-securitisation cases covering gross
  JTD, maturity scaling, netting, HBR, bucket capital, and category capital.
- `drc_nonsec_v2/`: generated U.S. NPR 2.0 non-securitisation integration
  fixture with manifest checksums and broader deterministic coverage.
- `drc_eu_nonsec_v1/`: static EU CRR3 non-securitisation cases covering
  Article 325w gross JTD/LGD, Article 325x netting and maturity weighting,
  Article 325y HBR/risk weights, and ECAI/CQS mapping citations.
- `drc_pra_nonsec_v1/`: static PRA UK CRR non-securitisation cases covering
  Article 325w gross JTD/LGD, Article 325x netting and maturity weighting,
  and Article 325y HBR/risk weights.
- `drc_sec_nonctp_v1/`: static U.S. NPR 2.0 securitisation non-CTP cases.
- `drc_basel_sec_nonctp_v1/`: static Basel MAR22 securitisation non-CTP cases
  with typed MAR22.34 risk-weight evidence and fair-value cap evidence.
- `drc_eu_sec_nonctp_v1/`: static EU CRR3 securitisation non-CTP cases with
  typed Article 325aa risk-weight evidence, fair-value cap evidence, and
  explicit offset-group evidence.
- `drc_ctp_v1/`: static U.S. NPR 2.0 CTP cases with replicated tranche and
  index-offset treatment.
- `drc_basel_ctp_v1/`: static Basel MAR22 CTP cases with typed MAR22.42
  risk-weight evidence and replicated tranche/index-offset treatment.
- `drc_eu_ctp_v1/`: static EU CRR3 CTP cases with typed Article 325ad
  banking-book risk-weight evidence, decomposition evidence, and explicit
  offset-group evidence.
- `handoff/`: minimal Parquet tables for the package Arrow handoff path.

## Boundary

The canonical DRC fixture shape is DRC-native. It mirrors the package inputs
that the capital layer already consumes:

- `DrcCalculationContext`
- `DrcPosition`
- `DrcFxRate`
- `DrcRiskWeightEvidence`
- `DrcFairValueCapEvidence`
- run-scoped CTP offset-group and risk-weight maps

Vendor rows are not the canonical regression fixture schema. Client ETL should
map vendor feeds into the DRC-native Arrow table contract or frozen dataclasses
before capital calculation. The package also exposes `adapt_drc_crif_rows` as a
DRC-owned CRIF/vendor ingress helper that returns canonical positions,
class-specific Arrow handoffs, or deterministic rejected-row diagnostics.

## Files

`packages/frtb-drc/tests/fixtures/drc_nonsec_v1/` contains:

- `positions.json`: synthetic canonical non-securitisation positions.
- `expected_outputs.json`: selected deterministic outputs across gross JTD,
  maturity weighting, net JTD, bucket capital, category capital, and total DRC.
- `fixture_loader.py`: loader for row-path tests.
- `README.md`: case-level intent and citation ids.

`packages/frtb-drc/tests/fixtures/drc_nonsec_v2/` contains:

- `positions.json`: generated canonical positions plus run context.
- `expected_outputs.json`: golden calculation outputs, input hash, profile
  hash, result JSON hash, and stage-level breakdowns.
- `manifest.json`: fixture id, schema version, and SHA-256 checksums for the
  generated files.

`packages/frtb-drc/tests/fixtures/drc_eu_nonsec_v1/` contains:

- `positions.json`: static EU CRR3 non-securitisation positions and context.
- `expected_outputs.json`: selected deterministic outputs across gross JTD,
  maturity weighting, net JTD, bucket capital, category capital, citation ids,
  and total DRC.
- `README.md`: case-level intent and CRR3/ECAI citation ids.

`packages/frtb-drc/tests/fixtures/drc_pra_nonsec_v1/` contains:

- `positions.json`: static PRA UK CRR non-securitisation positions and context.
- `expected_outputs.json`: selected deterministic outputs across gross JTD,
  maturity weighting, net JTD, bucket capital, category capital, citation ids,
  and total DRC.
- `README.md`: case-level intent and PRA Article 325w/x/y citation ids.

`packages/frtb-drc/tests/fixtures/drc_sec_nonctp_v1/` contains:

- `positions.json`: static securitisation non-CTP positions and context.
- `expected_outputs.json`: hand-checked expected total and selected stage
  outputs.
- `README.md`: fixture intent and hand-checked capital explanation.

`packages/frtb-drc/tests/fixtures/drc_basel_sec_nonctp_v1/` contains:

- `positions.json`: static Basel MAR22 securitisation non-CTP positions,
  context, typed risk-weight evidence, and fair-value cap evidence.
- `expected_outputs.json`: expected total and selected outputs.
- `README.md`: fixture intent and MAR22.34 evidence boundary.

`packages/frtb-drc/tests/fixtures/drc_eu_sec_nonctp_v1/` contains:

- `positions.json`: static EU CRR3 securitisation non-CTP positions, context,
  typed risk-weight evidence, fair-value cap evidence, and explicit
  offset-group evidence.
- `expected_outputs.json`: expected total and selected outputs.
- `README.md`: fixture intent and Article 325z/325aa evidence boundary.

`packages/frtb-drc/tests/fixtures/drc_ctp_v1/` contains:

- `positions.json`: static CTP positions, context, CTP risk weights, and
  offset-group inputs.
- `expected_outputs.json`: expected total and selected outputs.
- `README.md`: hand-checked CTP HBR and bucket-capital calculation.

`packages/frtb-drc/tests/fixtures/drc_basel_ctp_v1/` contains:

- `positions.json`: static Basel MAR22 CTP positions, context, typed MAR22.42
  risk-weight evidence, and offset-group inputs.
- `expected_outputs.json`: expected total and selected outputs.
- `README.md`: fixture intent and MAR22.42 evidence boundary.

`packages/frtb-drc/tests/fixtures/drc_eu_ctp_v1/` contains:

- `positions.json`: static EU CRR3 CTP positions, context, typed Article 325ad
  banking-book risk-weight evidence, decomposition evidence, and explicit
  offset-group inputs.
- `expected_outputs.json`: expected total and selected outputs.
- `README.md`: fixture intent and Article 325ab-325ad evidence boundary.

`packages/frtb-drc/tests/fixtures/handoff/` contains minimal Parquet examples
for the three public Arrow table families:

- `drc_nonsec_minimal.parquet`
- `drc_securitisation_non_ctp_minimal.parquet`
- `drc_ctp_minimal.parquet`

## Fixture Generation

`drc_nonsec_v2/` is generated by:

```bash
uv run python packages/frtb-drc/scripts/generate_fixture.py \
  --out packages/frtb-drc/tests/fixtures/drc_nonsec_v2
```

From `packages/frtb-drc`, the equivalent command is:

```bash
uv run python scripts/generate_fixture.py --out tests/fixtures/drc_nonsec_v2
```

The generator serializes `frtb_drc.demo_data.ALL_POSITIONS` and
`frtb_drc.demo_data.DEMO_CONTEXT`, calculates capital with
`calculate_drc_capital`, writes expected outputs, and records SHA-256 checksums
in `manifest.json`.

Other DRC fixture packs are static hand-checked or profile-specific fixtures.
Update those files directly when their fixture contract changes.

## Production Input Lineage

Production-style DRC runs should carry stable source lineage on every accepted
position and reference-data overlay. The canonical dataclasses expose
`DrcSourceLineage` with:

- source system,
- source file,
- source row id,
- optional source-column map.

The Arrow handoff path carries position lineage through `lineage_source_system`,
`lineage_source_file`, and `source_row_id` columns. Batch builders preserve
`source_hash`, `handoff_hash`, adapter diagnostics, lineage-present flags, and
per-row citation ids so audit output and replay can distinguish source content,
normalized table content, and package-owned calculation inputs.

Run-scoped reference overlays belong on `DrcCalculationContext`, not in the
position table unless the public context explicitly supports that shape. This
includes FX rates, securitisation risk-weight evidence, CTP risk weights, CTP
offset groups, and fair-value cap evidence.

## Arrow Table Handoff

High-volume tabular inputs should enter through these public normalizers and
batch builders:

| DRC class | Normalize | Build batch |
| --- | --- | --- |
| Non-securitisation | `normalize_drc_nonsec_arrow_table(...)` | `build_drc_nonsec_batch_from_arrow(..., profile_id=...)` |
| Securitisation non-CTP | `normalize_drc_securitisation_non_ctp_arrow_table(...)` | `build_drc_securitisation_non_ctp_batch_from_arrow(...)` |
| CTP | `normalize_drc_ctp_arrow_table(...)` | `build_drc_ctp_batch_from_arrow(...)` |

The Python `ColumnSpec` tuples are the source of truth:

- `DRC_NONSEC_ARROW_COLUMN_SPECS`
- `DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS`
- `DRC_CTP_ARROW_COLUMN_SPECS`

These specs accept documented aliases, normalize to canonical snake_case names,
and enforce required columns, null policy, and logical type before NumPy batch
construction. Calculation kernels consume package-owned batches, not
`pyarrow.Table` objects.

Each Arrow table must contain one DRC class only. Mixed class input must be
split into class-specific tables before normalization and batch construction.

### Required Column Families

Non-securitisation tables carry:

- position id,
- source row id,
- desk id,
- legal entity,
- risk class,
- instrument type,
- default direction,
- issuer id,
- bucket key,
- seniority,
- credit quality,
- notional,
- maturity years,
- currency,
- lineage source system and file,
- optional tranche and index ids,
- optional market value and cumulative P&L,
- optional LGD override,
- optional defaulted/GSE/PSE/covered-bond flags,
- optional citation ids.

Securitisation non-CTP tables use the same canonical columns, but seniority and
credit quality are optional because profile-specific securitisation risk
weights are supplied through context evidence. `issuer_id` may be null when the
tranche or securitisation key supplies the aggregation identity required by the
package path.

CTP tables use the same canonical columns, but issuer id, seniority, and credit
quality are optional. CTP risk weights and offset groups are supplied through
the calculation context where required.

## Reference Overlay Rules

Reference overlays take precedence only through fields exposed on
`DrcCalculationContext`. The package validates missing and unused map entries.
The following conditions fail closed rather than silently producing zero or
synthetic capital:

- missing FX rates for non-base-currency rows,
- missing securitisation non-CTP risk weights or typed evidence,
- stale or incomplete fair-value cap evidence,
- missing CTP risk weights, typed evidence, or offset groups where required,
- unsupported profile/risk-class combinations,
- unsupported decomposition evidence.

## Sign Conventions

DRC inputs use explicit default direction rather than inferring long or short
from accounting signs. The key conventions are:

- `default_direction` is `LONG` or `SHORT`.
- `notional`, `market_value`, and `cumulative_pnl` are interpreted according to
  the package's gross-JTD and fair-value-cap rules for the selected risk class.
- `currency` identifies the source currency; conversion to the context base
  currency requires explicit FX rates when the source currency differs.

Do not flip signs inside fixture loaders or batch builders to make a test pass.
If a vendor feed uses a different sign convention, normalize it in client ETL or
call `adapt_drc_crif_rows` with an explicit `DrcCrifDirectionStrategy`.
Ambiguous or zero signs are rejected before capital calculation.

## Golden Outputs

`expected_outputs.json` files store selected deterministic outputs rather than
full result snapshots. Depending on the fixture, they cover:

- input count and input hash,
- gross JTD,
- maturity weights,
- maturity-scaled JTD,
- net JTD and rejected offsets,
- HBR,
- bucket capital,
- category capital,
- total DRC,
- result JSON hash.

Tests compare floating-point values with deterministic tolerances and compare
categorical outputs, citations, rejected-offset reasons, and profile support
outcomes exactly. These fixtures are drift gates for the current calculation
contract, not independent regulatory benchmarks.

## Regeneration Rules

When changing generated non-securitisation fixture schema or calculation
semantics:

1. Update `packages/frtb-drc/scripts/generate_fixture.py` or the demo data it
   serializes.
2. Regenerate `drc_nonsec_v2/`:

```bash
uv run python packages/frtb-drc/scripts/generate_fixture.py \
  --out packages/frtb-drc/tests/fixtures/drc_nonsec_v2
```

3. Review diffs in `positions.json`, `expected_outputs.json`, and
   `manifest.json`.
4. Run the affected DRC tests, for example:

```bash
uv run pytest packages/frtb-drc/tests/test_drc_nonsec_v2_fixture.py \
  packages/frtb-drc/tests/test_drc_arrow_batch.py
```

When changing static fixture packs, update the relevant `README.md`,
`positions.json`, and `expected_outputs.json`, then run the fixture-specific
test plus `packages/frtb-drc/tests/test_drc_arrow_batch.py` if the Arrow path is
affected.

For broader DRC changes, run:

```bash
uv run pytest packages/frtb-drc/tests
```

Before publishing package documentation changes, run `make quality-control`
from the repository root when practical.

If only generated timestamps, checksums without content changes, or incidental
ordering changed, fix fixture determinism before accepting the update.
