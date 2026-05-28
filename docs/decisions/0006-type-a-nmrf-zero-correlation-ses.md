# 6. Type A NMRF zero-correlation SES aggregation

Date: 2026-05-28

## Status

Accepted

## Context

The Fed NPR 2.0 profile in `frtb-ima` uses a Type A / Type B NMRF taxonomy.
The package must route non-modellable risk factors consistently through IMCC
and SES and preserve an auditable aggregation breakdown.

Earlier prototype behaviour used more conservative linear Type A aggregation.
The accuracy audit corrected that to a zero-correlation root-sum-square
treatment and documented the package policy in
`REGULATORY_ASSUMPTIONS.md`, `REGULATORY_TRACEABILITY.md`, and
`NPR_2_0_MARKET_RISK.yml`.

## Decision

For the Fed NPR 2.0 profile:

- Type A NMRFs are routed to both IMCC and SES.
- Type B NMRFs are routed to SES only.
- Type A SES aggregates as zero-correlation root-sum-square:

```text
SES_A = sqrt(sum_i(SES_A_i^2))
```

- Type B SES uses the configured policy correlation parameter
  `RegulatoryPolicy.type_b_ses_rho`.

The policy value and routing are material model choices. Any change to Type A
routing, Type A aggregation mode, Type B routing, or Type B rho requires ADR
review under ADR 0005.

## Consequences

**Positive:**

- Type A aggregation no longer overstates capital by linear summation.
- The calculation is decomposed in `SESAggregationResult` for audit review.
- The policy is explicit in code, tests, traceability, and documentation.

**Negative:**

- Cross-regime semantics are not portable. ECB/PRA profiles do not treat Type A
  / Type B labels as native terminology and keep explicit unsupported-feature
  guards where needed.

## References

- `packages/frtb-ima/src/frtb_ima/nmrf.py`.
- `packages/frtb-ima/src/frtb_ima/regimes.py`.
- `packages/frtb-ima/docs/REGULATORY_ASSUMPTIONS.md`.
- `packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md`.
- `packages/frtb-ima/docs/requirements/NPR_2_0_MARKET_RISK.yml`.
- ADR 0005.
