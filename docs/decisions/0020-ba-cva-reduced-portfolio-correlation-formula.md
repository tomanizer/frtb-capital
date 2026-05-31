# 20. Reduced BA-CVA portfolio correlation formula (ρ²/(1−ρ²))

Date: 2026-05-31

## Status

Accepted

## Context

A regulatory-compliance audit of `frtb-cva` found that the reduced BA-CVA
portfolio aggregation in `frtb_cva.ba_cva.calculate_reduced_portfolio`
misweighted the systematic and idiosyncratic terms.

The implementation computed:

```text
K_portfolio = sqrt( ρ · (Σ_c SCVA_c)²  +  (1 − ρ) · Σ_c SCVA_c² )
```

Basel **MAR50.14** requires:

```text
K_reduced = DS · sqrt( ( ρ · Σ_c SCVA_c )²  +  (1 − ρ²) · Σ_c SCVA_c² )
```

i.e. the systematic term is `ρ² · (Σ SCVA)²` and the idiosyncratic term is
`(1 − ρ²) · Σ SCVA²`, with `ρ = 0.50` and the discount scalar `DS = 0.65`.

With `ρ = 0.5` the correct weights are **0.25 / 0.75**, but the code applied
**0.50 / 0.50** (`ρ` where `ρ²` was required, and `1 − ρ` where `1 − ρ²` was
required). The two expressions coincide only when a single counterparty is
present, so the error was invisible to single-counterparty tests, and the
multi-counterparty reconciliation test re-derived the same incorrect expression
as its own oracle rather than checking against MAR50.14.

The discount scalar `DS = 0.65` (applied outside the square root) was already
correct and is unchanged.

## Decision

Implement the MAR50.14 form exactly:

```python
k_portfolio = math.sqrt((rho * sum_scva) ** 2 + (1.0 - rho**2) * sum_scva_squared)
```

Replace the tautological reconciliation test with an independent oracle that
uses hard-coded `0.25 / 0.75` weights derived from each counterparty's realised
stand-alone SCVA, plus a regression guard asserting the corrected value is
strictly below the previous (over-stated) value for any multi-counterparty
portfolio.

This change is scoped to the reduced BA-CVA portfolio aggregation only. A
separate, independently-tracked finding on the MAR50.15 stand-alone SCVA factor
(`α` applied as a multiplier instead of `1/α`) is **not** addressed here.

## Consequences

- Reduced BA-CVA portfolio capital decreases for any portfolio with more than
  one counterparty (the previous form over-stated the systematic component and
  under-credited diversification). Single-counterparty portfolios are unchanged.
- `frtb-cva` numerical outputs change; version bump is deferred to a `release/*`
  PR per ADR 0015 (changelog fragment `packages/frtb-cva/changelog.d/240.fix.md`).
- The package remains `ValidationStatus.PENDING`; this correction does not
  constitute independent model validation.

## References

- Basel Framework MAR50.14 (reduced BA-CVA aggregation; ρ = 0.5, DS = 0.65).
- GitHub issue #240.
- Related open finding: MAR50.15 stand-alone SCVA `1/α` factor.
