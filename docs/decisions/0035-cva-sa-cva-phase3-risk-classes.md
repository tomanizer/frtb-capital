# 35. SA-CVA phase 3 remaining risk classes (FX, CCS, RCS, equity, commodity, vega)

Date: 2026-05-31

## Status

Accepted

## Context

Issues #214/#215 delivered SA-CVA GIRR delta and the shared aggregation
framework. Issue #216 extends coverage to the remaining six MAR50 risk
classes required for a complete SA-CVA calculation:

- FX delta (MAR50.59-MAR50.61) and FX vega (MAR50.60)
- Counterparty credit spread (CCS) delta (MAR50.63-MAR50.65)
- Reference credit spread (RCS) delta (MAR50.66-MAR50.68) and vega (MAR50.69)
- Equity delta (MAR50.70-MAR50.72) and vega (MAR50.73)
- Commodity delta (MAR50.74-MAR50.76) and vega (MAR50.77)
- GIRR vega (MAR50.58, using the existing GIRR risk-weight infrastructure)

Each risk class introduces: a risk-weight table, an intra-bucket correlation
function, an inter-bucket gamma function, and a public `calculate_*_capital`
entry point. All calculations feed through the shared `aggregate_intra_bucket`
and `aggregate_inter_bucket` kernels in `frtb_cva.aggregation`.

## Decision

### Intra-bucket correlations

Intra-bucket correlation parameters follow the Basel standard precisely:

| Risk class | Same name | Distinct name |
|---|---|---|
| GIRR delta (from phase 2) | tenor-dependent, MAR50.56 | tenor-dependent, MAR50.56 |
| GIRR vega | 1.0 | — (single IR-vol factor per bucket) |
| FX delta | 1.0 | — (single FX factor per bucket-pair) |
| FX vega | 1.0 | — |
| CCS delta | entity/quality/tenor-dependent, MAR50.63 | entity/quality/tenor-dependent |
| RCS delta | 1.0 | 0.50, MAR50.68 |
| RCS vega | 1.0 | 0.50, MAR50.68 |
| Equity delta | 1.0 | 0.15 (buckets 1-10), 0.25 (buckets 11-13), MAR50.72 |
| Equity vega | 1.0 | 0.15 (buckets 1-10), 0.25 (buckets 11-13), MAR50.72 |
| Commodity delta | 1.0 | 0.20, MAR50.76 |
| Commodity vega | 1.0 | 0.20, MAR50.76 |

### CCS vega prohibition

CCS vega sensitivity is not permitted under MAR50.45 and MAR50.63.
`calculate_sa_cva_capital` raises `CvaInputError` if CCS vega sensitivities
are submitted.

### CCS qualified-index bucket 8

Bucket 8 (the qualified-index CCS bucket) requires a regulatory mapping
that has not yet been delivered. Inputs referencing this bucket raise
`CvaInputError` with a clear unsupported message.

### Reference data organisation

All intra-bucket, inter-bucket, and risk-weight tables for the six new risk
classes are housed in `frtb_cva.sa_cva_reference_data` alongside the existing
GIRR and CCS tables. Risk-class-specific calculation logic lives under
`frtb_cva.risk_classes.*` with one module per risk class.

## Consequences

- SA-CVA total capital can now be computed for all currently supported
  risk classes; portfolios that include CCS vega or bucket-8 exposures
  will receive an explicit unsupported error rather than silently producing
  incomplete capital.
- CCS `parse_ccs_entity_key` is cached with `functools.cache` to avoid
  redundant parsing in the O(N²) intra-bucket correlation matrix loop.
- Outputs are audit-serialisable via `frtb_cva.audit.serialize_cva_result`
  with risk-class and bucket breakdowns.

## References

- Basel Framework MAR50.54-MAR50.77 (SA-CVA risk-class capital).
- GitHub issue #216 (SA-CVA phase 3 remaining risk classes).
