# FRTB-CVA Arrow Batch Triage

Issue: #301

Latest optimization issue: #318

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

The #318 batch path sorts netting-set ids and counterparty ids with NumPy once,
then walks grouped index slices in deterministic counterparty/netting-set order.
It also precomputes BA-CVA profile scalars and counterparty risk weights before
line construction, avoiding repeated profile lookups for every netting-set row.

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

The #318 SA-CVA path routes risk-class/risk-measure groups with NumPy masks
against the package-owned arrays before constructing weighted sensitivities.
Unsupported path checks remain explicit, including the MAR50.45/MAR50.63
fail-closed treatment for CCS vega.

## Arrow Conversion

The CVA Arrow batch now avoids whole-column `to_pylist()` conversions for the
accepted high-volume columns. Numeric float64 Arrow chunks use zero-copy NumPy
views where Arrow exposes a contiguous non-null buffer; nullable numeric columns
are filled through Arrow compute before NumPy conversion. Dictionary-encoded
and chunked text columns decode by chunk into object arrays, preserving nulls
without building a Python list for the whole column. Boolean columns use Arrow
compute fill paths when physically boolean and fall back to object arrays only
when the handoff carries string-like booleans.

Batch builders adopt caller-supplied NumPy arrays through read-only views when
`copy_arrays=False`, so the immutable batch contract no longer freezes the
caller-owned arrays. Required numeric arrays still reject non-finite values, and
optional numeric arrays still permit null/NaN but reject infinities.

## Measurement Harness

`packages/frtb-cva/scripts/benchmark_cva_target_scale.py` compares:

- BA-CVA row calculation;
- BA-CVA column batch build and calculation;
- BA-CVA Arrow batch build and batch calculation;
- SA-CVA row calculation;
- SA-CVA sensitivity column batch build and calculation.

The harness reports timings, traced peak memory, payload hashes, capital
deltas, and accepted-input dataclass materialization counters. It intentionally
uses Arrow and the package APIs directly, with no dataframe dependency, so it
measures the handoff and kernel architecture rather than a dataframe engine.

On the local 2026-06-01 run with 100 counterparties, 1,000 BA-CVA netting sets,
and 100,000 SA-CVA sensitivities, payload hashes matched row calculation for
BA-CVA column batch, BA-CVA Arrow batch, and SA-CVA column batch. Capital deltas
were all 0.0 and all batch accepted-input dataclass counters were 0. The SA-CVA
column batch calculation was 6.36s versus 10.25s for the row path; BA-CVA
calculation remained dominated by required audit line emission at this scale,
with row 0.053s, column batch 0.068s, and Arrow batch 0.089s.

## Fail-Closed Cases

The batch builders reject:

- missing required lineage columns in Arrow batches;
- duplicate stable ids;
- netting sets referencing unknown counterparties at calculation time;
- unsupported SA-CVA risk-class/risk-measure paths;
- invalid qualified-index routing or look-through-required rows;
- ambiguous booleans or non-finite numeric values.

Rejected rows and adapter diagnostics remain in the `NormalizedArrowTable`
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
