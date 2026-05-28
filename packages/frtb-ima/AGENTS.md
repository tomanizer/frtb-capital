# AGENTS.md — Codex guidance for FRTB-IMA

## Project identity

This package is the migrated IMA component inside the `frtb-capital` monorepo.
It contains a prototype NPR 2.0-style FRTB IMA market-risk capital calculator.

The goal is not production regulatory compliance. The goal is to create a transparent, testable prototype that demonstrates how an existing risk engine could generate scenario P&L vectors and NMRF stress artifacts while an ex-post capital layer assembles IMA-style capital.

## Scope boundary

This package covers the IMA model-eligible desk capital path only. **SBM, DRC,
RRAO, and CVA are planned sibling packages in this monorepo**; do not add those
calculations here. SA fallback is an orchestration concern that composes SBM,
DRC, and RRAO. The handoff contract from this package is a desk-level capital
result and eligibility signal; aggregation across desks is an orchestration-
layer concern outside `packages/frtb-ima`.

## Regulatory caution

Treat all U.S. NPR 2.0 content as proposed-rule material. Do not present
outputs as final regulatory capital.

Key prototype assumptions:
- Expected shortfall starts from 10-day scenario P&L vectors.
- Liquidity horizon adjustment is done from nested scenario vectors, not by scaling one final ES scalar.
- Risk factors classify as `MODELLABLE`, `TYPE_A_NMRF`, or `TYPE_B_NMRF`.
- Type A NMRFs go into both IMCC and SES.
- Type B NMRFs go into SES only with conservative aggregation.
- NMRF direct, stepwise, and full-revaluation pricing remains upstream; this package selects methods, emits valuation specs, reconciles and validates returned artifacts, and aggregates SES.
- Fed NPR PLA uses a Kolmogorov-Smirnov statistic over HPL and RTPL vectors; ECB/PRA comparison profiles also compute Spearman and use the worse joint zone.
- Backtesting counts APL and HPL exceptions over 250 business days at both 97.5% and 99.0% VaR levels.
- Runtime logging is structured and scalar-only at policy-wrapper boundaries; post-run audit records use serialisable dataclasses and NDJSON.

## Coding style

- Use Python 3.11+.
- Prefer dataclasses, enums, and pure functions.
- Keep dependencies minimal.
- Synthetic data only.
- Add unit tests for every calculation.
- Favor clarity over cleverness.
- Include explanatory comments for regulatory formulas.
- Do not introduce web/API calls.
- Do not require proprietary market data.

## Review focus

When reviewing or changing code, focus on:
- Correct scenario-vector granularity (nested LH vectors, not scalar scaling).
- No inappropriate final-scalar liquidity-horizon scaling.
- Deterministic tests.
- Clear risk-factor classification logic.
- Explicit `DeskEligibilityStatus` handoff before capital assembly.
- Separation of risk engine outputs from capital aggregation.
- Clear unsupported-feature behavior where ECB/PRA or full regulatory workflows are not implemented.
- Good documentation of assumptions and limitations.
- No SBM, DRC, RRAO, CVA, SA-composition, or firm-level consolidation
  calculations in this package.
