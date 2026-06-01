# FRTB-DRC Arrow Batch Triage

This is the point-in-time data-shape and hotspot assessment for issue #299.
The scope is the implemented non-securitisation DRC path only; securitisation
and CTP paths remain fail-closed.

## Data Shape

The high-volume DRC input surface is position-grained. The kernel needs stable
position ids, source row ids, desk and legal entity, risk class, instrument
type, long/short default direction, issuer or tranche key, bucket, seniority,
credit quality, notional, market value or cumulative P&L, maturity, currency,
default flags, and lineage metadata. For the supported non-securitisation path
the batch requires issuer, bucket, seniority, credit quality, notional,
maturity, and currency columns.

The package-owned batch stores those fields as immutable NumPy arrays plus
typed metadata:

- object arrays for ids, issuer, bucket, seniority, credit quality, currency,
  and lineage;
- float arrays for notional, market value, cumulative P&L, maturity, and LGD
  override;
- boolean arrays for default/GSE/PSE/covered-bond flags;
- package metadata for source hash, handoff hash, diagnostics, citations, and
  source column maps.

## Hotspots

The row API currently validates and sorts `DrcPosition` dataclasses, creates
per-row gross JTD dataclasses, creates per-row maturity-scaled dataclasses,
groups by bucket and issuer, applies same-obligor seniority netting, then
builds bucket/category result dataclasses. At volume, the hot cost is not the
arithmetic; it is accepted-row object construction and repeated row scanning.

The batch path therefore keeps position, gross JTD, maturity weight, and scaled
JTD as arrays. It only materializes the compact public capital result and net
JTD audit records. This preserves deterministic lineage and existing result
contracts without requiring one `DrcPosition`, `GrossJtd`, or
`MaturityScaledJtd` object per accepted input row on the high-volume path.

## Architecture Decision

The regulatory kernel remains package Python and NumPy, not Polars, pandas, or
Arrow expression plans. Arrow is the handoff boundary; DRC owns interpretation
of issuer/seniority netting, LGD lookup, maturity floors, HBR, risk weights,
citations, and fail-closed unsupported scope. This keeps grouping and sort
semantics explicit in DRC code while still avoiding row-wise dataclass churn for
accepted high-volume input.

## Implemented Path

The implemented high-volume path is:

1. `normalize_drc_nonsec_arrow_table` normalizes a canonical Arrow table to the
   DRC non-securitisation handoff contract.
2. `build_drc_nonsec_batch_from_handoff` builds `DrcPositionBatch` without
   accepted-row `DrcPosition` materialization.
3. `calculate_drc_capital_from_batch` computes gross JTD arrays, maturity
   weight arrays, scaled JTD arrays, seniority netting, bucket DRC, category
   DRC, and total DRC.

The row API remains the compatibility path for callers that already hold
canonical dataclasses.

## Issue #316 Conversion and Batch Check

The issue #316 changes reduce Arrow handoff conversion overhead for DRC numeric,
boolean, dictionary-encoded text, and chunked columns. Required `float64`
columns now use Arrow-to-NumPy views where the Arrow buffer permits it; nullable
optional floats use an explicit null-to-`NaN` policy; and optional booleans use
an explicit null-to-`False` policy. Gross JTD LGD lookup is now performed by
seniority/defaulted masks rather than one reference-data call per row. The
same-obligor netting loop remains explicit Python because it carries regulatory
seniority-offset audit records and deterministic source-id ordering.

The benchmark harness is `benchmarks/drc_adapter_harness.py` and can be run
with:

```bash
make drc-benchmark
```

On macOS-26.5 arm64 / Python 3.11.15, a 5,000-row synthetic non-securitisation
run recorded:

- row-compatible dataclass construction: 0.421s
- row-compatible calculation: 4.802s
- row-compatible audit serialization: 14.132s
- Arrow table construction: 0.253s
- handoff normalization: 0.004s
- batch construction: 1.422s
- batch calculation: 0.549s
- batch audit serialization: 1.457s
- accepted-row dataclasses on the Arrow path: 0
- row and batch total DRC absolute delta: 0.0

The result confirms that the high-volume DRC path avoids accepted-row
`DrcPosition`, `GrossJtd`, and `MaturityScaledJtd` materialization while
preserving the public capital number and net-JTD audit result.
