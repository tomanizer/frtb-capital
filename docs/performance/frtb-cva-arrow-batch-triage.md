# FRTB-CVA Arrow Batch Triage

Issue: #301

## Decision

CVA high-volume inputs use Arrow as the external handoff, then convert into
package-owned immutable NumPy batches before capital calculation. The regulatory
kernel keeps BA-CVA and SA-CVA rule interpretation in explicit package code
rather than in dataframe expressions.

The row/dataclass API remains as compatibility and audit surface. The batch
entrypoints do not materialize accepted-row `CvaCounterparty`, `CvaNettingSet`,
`CvaHedge`, or `SaCvaSensitivity` dataclasses during calculation. They still
emit existing public result dataclasses, because those are the package audit
contract.

## BA-CVA Shape

Counterparty batches carry:

- `counterparty_id`, `desk_id`, `legal_entity`;
- `sector`, `credit_quality`, and `region`;
- `source_row_id`, source lineage fields, source and handoff hashes.

Netting-set batches carry:

- `netting_set_id`, `counterparty_id`;
- `ead`, `effective_maturity`, `discount_factor`;
- `currency`, `sign_convention`, `uses_imm_ead`;
- carve-out and explicit-discount flags;
- source row, lineage, source hash, and handoff hash.

The hotspot is netting-set line construction and counterparty aggregation. The
batch path validates ids and numeric domains once, groups netting-set row
indexes by counterparty id, and calculates MAR50.14 reduced BA-CVA and
MAR50.17-MAR50.26 full BA-CVA without rebuilding canonical input rows.

## Hedge Shape

Hedge batches carry:

- `hedge_id`, `counterparty_id`, hedge type, notional, remaining maturity, and
  discount factor;
- eligibility, internal/external flags, eligibility evidence, rejection reason,
  and SA-CVA risk-class metadata;
- reference sector, credit quality, region, and reference relation;
- source row, lineage, source hash, and handoff hash.

The hotspot is eligibility routing and hedge recognition. The batch path mirrors
the row eligibility decisions directly from arrays, then emits the existing
`BaCvaHedgeRecognitionLine` audit records.

## SA-CVA Shape

Sensitivity batches carry:

- `sensitivity_id`, risk class, risk measure, sensitivity tag;
- bucket/risk-factor key, tenor, amount, amount currency, sign convention;
- volatility input for vega rows;
- hedge id for hedge sensitivities;
- qualified-index treatment, sector concentration, dominant-sector, and remap
  metadata;
- source row, lineage, source hash, and handoff hash.

The hotspot is weighted-sensitivity grouping. The batch path groups accepted
array rows by effective risk-factor key, applies qualified-index bucket routing
in package code, and only creates `SaCvaWeightedSensitivity` records after
grouping. It then reuses the existing bucket and inter-bucket aggregation code.

## Fail-Closed Cases

The batch builders reject:

- missing required lineage columns in Arrow handoffs;
- duplicate stable ids;
- netting sets referencing unknown counterparties at calculation time;
- unsupported SA-CVA risk-class/risk-measure paths;
- invalid qualified-index routing or look-through-required rows;
- ambiguous booleans or non-finite numeric values.

Rejected rows and adapter diagnostics remain in the `NormalizedTabularHandoff`
and are copied into the package-owned batch diagnostics.

## Why Not Dataframe Kernels

Polars or Arrow expressions are suitable for adapter-side normalization and
filtering, but not as the canonical regulatory kernel here. CVA contains
branch-heavy rules: BA-CVA discount-factor resolution, hedge eligibility,
sector/quality risk weights, qualified-index remapping, weighted-sensitivity
grouping, and risk-class aggregation. Keeping those branches in typed package
code preserves citation placement, deterministic audit records, and line-level
reconciliation while still avoiding row-wise input dataclass construction on
volume paths.
