# 7. PLA metric policy by regime

Date: 2026-05-28

## Status

Accepted

## Context

Profit-and-loss attribution is a desk-level model-eligibility diagnostic. The
Fed NPR 2.0 profile currently uses a Kolmogorov-Smirnov metric over HPL and
RTPL vectors, while EU/PRA comparison profiles also require a Spearman
rank-correlation metric and apply the worse joint zone.

The package needs a clear policy boundary so Fed runs do not silently inherit
EU/PRA comparison mechanics and EU/PRA comparison runs do not omit Spearman.

## Decision

Use `RegulatoryPolicy.pla_metrics_required` to select the metric set:

- Fed NPR 2.0: `KS_ONLY`.
- ECB CRR3 and PRA UK CRR comparison profiles: `KS_AND_SPEARMAN`.

For KS+Spearman profiles, the authoritative PLA zone is the worse of the KS and
Spearman zones using the configured ordered zone labels. Thresholds are policy
fields with citation metadata in `RegulatoryPolicy.cited_by`.

Any change to PLA metric selection, threshold defaults, policy-window length,
zone ordering, or joint-zone logic is material under ADR 0005.

## Consequences

**Positive:**

- Fed profile behaviour stays explicit and testable.
- EU/PRA comparison paths expose Spearman rather than treating it as an
  undocumented post-processing step.
- Future regime-specific PLA refinements can be added through policy rather
  than hardcoding in calculators.

**Negative:**

- PLA documentation must distinguish Fed and comparison-profile behaviour.
- EU/PRA profiles remain partial comparison profiles, not full own-funds
  calculators.

## References

- [packages/frtb-ima/src/frtb_ima/pla.py](../../packages/frtb-ima/src/frtb_ima/pla.py).
- [packages/frtb-ima/src/frtb_ima/regimes.py](../../packages/frtb-ima/src/frtb_ima/regimes.py).
- [packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md](../../packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md).
- [packages/frtb-ima/docs/requirements/NPR_2_0_MARKET_RISK.yml](../../packages/frtb-ima/docs/requirements/NPR_2_0_MARKET_RISK.yml).
- [ADR 0005](0005-material-change-policy.md).
