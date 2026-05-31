# 21. BA-CVA stand-alone SCVA applies alpha as divisor (1/α), not multiplier

Date: 2026-05-31

## Status

Accepted

## Context

A regulatory-compliance audit of `frtb-cva` found that the netting-set
stand-alone capital in `frtb_cva.ba_cva.calculate_netting_set_standalone`
applied the supervisory factor α as a **multiplier**:

```text
SCVA = α · RW_c · M · EAD · DF        (incorrect)
```

Basel **MAR50.15** requires:

```text
SCVA_c = (1/α) · RW_c · Σ_NS( M_NS · EAD_NS · DF_NS ),   α = 1.4
```

α = 1.4 is applied as a **divisor** because it removes the conservatism already
embedded in the regulatory EAD (SA-CCR or IMM), avoiding double-counting.
Multiplying instead of dividing overstates every SCVA by a factor of α² = 1.96
relative to the regulation.

Because reduced BA-CVA portfolio capital (MAR50.14) is homogeneous degree 1 in
SCVA, `K_reduced` was also overstated by 1.4× for all portfolios.

The existing tests (`test_sovereign_ig_standalone_capital` and
`test_financial_hy_standalone_capital`) used `alpha * ...` as their own oracle,
encoding the bug rather than detecting it. The scaffold-fixture test pinned the
old wrong `K_reduced` value directly.

This finding is independent of issue #240 / ADR 0020, which corrects the
MAR50.14 portfolio correlation formula in the same file.

## Decision

Apply α as a divisor per MAR50.15:

```python
standalone = (
    risk_weight * netting_set.effective_maturity * netting_set.ead * discount_factor / alpha
)
```

Update the two existing standalone-capital test oracles to `... / _ALPHA`.

Add `test_netting_set_standalone_matches_mar50_15_formula`: an independent
oracle using the simplified IMM case (DF=1) where the expected value reduces to
a single multiplication `0.005 × 2.0 × 1_000_000 / 1.4`, plus a regression
guard asserting the corrected value is strictly below the previous
(α·RW·M·EAD·DF) value.

Update the scaffold fixture to express its pinned value as the derivation
`0.65 × 0.005 × 2.5 × 1e6 / 1.4` so the formula remains readable.

## Consequences

- Every netting-set SCVA decreases by a factor of α² = 1.96 (correct value is
  `1/1.4` of the old value, because old was `α × correct`; `α / (1/α) = α²`).
- `K_reduced` decreases proportionally for all portfolios.
- `frtb-cva` numerical outputs change; version bump is deferred to a `release/*`
  PR per ADR 0015 (changelog fragment `packages/frtb-cva/changelog.d/257.fix.md`).
- The `line.alpha` audit field continues to store `1.4` (the regulatory
  constant) unchanged; only `standalone_capital` changes.
- The package remains `ValidationStatus.PENDING`; this correction does not
  constitute independent model validation.

## References

- Basel Framework MAR50.15 (netting-set stand-alone CVA capital; α = 1.4).
- GitHub issue #257.
- Related fix: ADR 0020 / issue #240 (MAR50.14 portfolio correlation formula).
