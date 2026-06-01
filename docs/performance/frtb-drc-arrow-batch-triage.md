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
