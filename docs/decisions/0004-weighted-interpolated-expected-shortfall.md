# 4. Weighted interpolated expected shortfall estimator

Date: 2026-05-28

## Status

Accepted

## Context

`frtb-ima` originally used a discrete-ceil finite-sample expected shortfall
estimator: sort losses descending, take `ceil(n * (1 - alpha))` scenarios, and
average them. That is transparent and easy to test, but it jumps when the
confidence level or scenario count changes and fully includes the boundary
scenario even when only fractional tail mass remains.

Basel MAR33 and the U.S. NPR 2.0 expected-shortfall proposal define the tail
risk measure but do not prescribe this package's finite-sample interpolation
method. The interpolation method is therefore a material modelling choice that
must be explicit in policy configuration.

## Decision

Use a weighted interpolated expected shortfall estimator as the default
`RegulatoryPolicy.es_estimator` for the Fed NPR 2.0, ECB CRR3, and PRA UK CRR
profiles.

The estimator sorts losses descending, takes the `floor(n * (1 - alpha))` worst
losses fully, applies the remaining fractional tail mass to the next loss, and
divides by `n * (1 - alpha)`.

Keep the prior discrete-ceil estimator as `ESEstimator.DISCRETE_CEIL` for
explicit compatibility tests and sensitivity analysis. Calculation helpers must
receive an estimator explicitly or use a policy-aware wrapper.

## Consequences

**Positive:**

- Smoother finite-sample ES behaviour when the tail mass is fractional.
- The estimator choice is visible in `RegulatoryPolicy`, policy hashes, audit
  decomposition payloads, and fixture parameters.
- The original estimator remains available for regression comparisons.

**Negative:**

- Golden fixture values change because IMCC, LHA ES, NMRF SES, and
  stress-period scoring now consume the weighted estimator through policy.
- Historical comparisons must record the estimator used for each run.

## References

- Basel MAR33 expected shortfall.
- U.S. NPR 2.0 proposed expected-shortfall-based market risk measures.
- `tomanizer/frtb-capital` issue #9.
