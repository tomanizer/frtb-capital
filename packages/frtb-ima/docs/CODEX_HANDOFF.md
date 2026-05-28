# Codex handoff - FRTB-IMA

> **Agent document.** This brief is for Codex and other coding agents.
> Human-facing documentation starts at `README.md`. The authoritative coding
> standards and review checklist are in `CLAUDE.md`.

## One-line task

Maintain a transparent Python prototype of an NPR 2.0-style FRTB IMA capital
assembly layer in `tomanizer/frtb-capital`, under `packages/frtb-ima`.

## Scope boundary

This package is the IMA model-eligible desk capital path only.

**SA, DRC, and CVA are planned sibling packages in this monorepo.** Do not add
standardized approach, default risk charge, CVA capital, fallback capital,
firm-level consolidation, or legal-entity aggregation to this package. The
handoff contract from `packages/frtb-ima` is a desk-level `CapitalComponents`
result and a `DeskEligibilityStatus` signal. Aggregation across desks and
regimes is an orchestration-layer concern.

## Architecture

```text
Upstream risk engine
    -> RFET classifications known before valuation
    -> supplied historical risk-class loss series for stress-period selection
    -> upstream IMCC stressed-ES scenario preparation informed by selections
    -> NMRF method-selection evidence, instructions, and valuation specs
    -> 10-day scenario P&L vectors and NMRF stress artifacts
    -> ex-post capital aggregation layer (this package)
    -> DeskEligibilityStatus + CapitalComponents per desk
    -> structured JSON runtime logs and NDJSON desk audit records
```

## Current implemented milestone

- Risk-factor modellability classification (RFET scalar and audit-grade evidence).
- Liquidity-horizon-adjusted expected shortfall from nested scenario vectors.
- Constrained/unconstrained IMCC decomposition.
- Reduced-set 60-business-day / 75% variation-explained diagnostic.
- Vectorized stress-period selection by risk class from supplied historical
  loss/severity series.
- NMRF method evidence, valuation instructions, upstream valuation-run specs,
  artifact reconciliation, Type A/B routing, and SES aggregation.
- Fed NPR KS PLA over the 250-business-day policy window with optional date
  diagnostics.
- EU/PRA Spearman PLA and worse-of-KS/Spearman joint-zone logic.
- APL/HPL backtesting at 97.5% and 99.0% VaR with optional dated traces and
  official-holiday exclusions.
- Desk-level models-based capital and PLA add-on helper.
- `DeskEligibilityStatus` enum and `desk_eligibility_from_results` handoff
  guard in `capital.py`.
- Dependency-free structured JSON logging at policy-wrapper boundaries.
- `DeskAuditRecord` / `CapitalRunAuditLog` NDJSON artifacts and deterministic
  Markdown report rendering.
- Regulatory risk-factor category to liquidity-horizon mapping table,
  short-maturity rule, and weighted-average multi-underlying helpers.

## Build sequence completed

1. Bootstrap package, pyproject, tests.
2. Add data models.
3. Add expected shortfall.
4. Add liquidity horizon adjustment from nested vectors.
5. Add RFET / modellability classifier.
6. Add Type A / Type B NMRF SES aggregation.
7. Add NMRF method selection, valuation instructions/specs, valuation-run
   reconciliation, and stress artifacts.
8. Add IMCC aggregation.
9. Add PLA KS and backtesting.
10. Add capital assembly.
11. Add synthetic demo.
12. Add structured logging and NDJSON audit records.
13. Add vectorized stress-period selection from supplied historical loss series.
14. Add deterministic Markdown audit report rendering and `make audit`.
15. Add risk-factor category to liquidity-horizon mapping table helpers.
16. Add `DeskEligibilityStatus` and capital eligibility guard.
17. Add EU/PRA Spearman PLA metric and joint-zone logic.

## Current next workstreams

1. Coverage hardening - `stress_periods.py`, `nmrf_stress_spec.py`, and
   `nmrf_method_selection.py` are partial in the requirements registry. Add
   tests for stepwise/full-revaluation spec paths and direct robustness
   diagnostic branches.
2. Performance benchmark suite - 10,000 scenarios x 5 LH subsets x 5 risk
   classes x 100 desks plus audit serialization. Validate the NumPy-native
   design claim at target scale.

## Key warning

Do not calculate liquidity horizon adjustment by taking one final ES number and
multiplying by a square-root factor. The prototype must use scenario vectors by
nested liquidity-horizon subsets.
