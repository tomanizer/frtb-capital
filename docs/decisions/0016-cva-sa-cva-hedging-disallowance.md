# 16. SA-CVA GIRR delta hedging-disallowance term

Date: 2026-05-31

## Status

Accepted

## Context

Issue #220 identified that `frtb-cva` intra-bucket aggregation used a signed
cross-product form for the MAR50.55 indirect-hedge disallowance. When CVA and
hedge weighted sensitivities offset (opposite signs), that form contributed a
non-positive term under the square root, reducing bucket capital `K_b` instead
of penalising imperfect hedges.

Basel MAR50.55 requires an additive disallowance based on hedge weighted
sensitivities. The standard residual form is `R · Σ_k (WS_k^HDG)²`, which is
always non-negative and leaves a floor of `sqrt(R) · |WS^HDG|` when net
sensitivity cancels.

## Decision

Replace the signed cross-product implementation with:

```text
hedging_disallowance = R · Σ_k (WS_k^HDG)²
```

where `R = 0.01` (MAR50.55) and `WS^HDG` is the weighted hedge sensitivity per
risk factor in the bucket.

This change applies only to the delivered SA-CVA GIRR delta slice in
`frtb_cva.aggregation.aggregate_intra_bucket`.

## Consequences

- SA-CVA bucket capital increases for portfolios with material eligible hedges
  relative to the incorrect signed form; unhedged portfolios are unchanged.
- Audit serialization now emits SA-CVA risk-class and bucket breakdowns (issue
  #220 C1).
- Numerical regression tests pin the disallowance for an offsetting CVA/HDG pair.

## References

- Basel Framework MAR50.55 (indirect-hedge disallowance).
- CRR3 Art. 383(8) (EU transposition of the SA-CVA hedging disallowance).
- GitHub issue #220.
