# AGENTS.md — Codex guidance for FRTB-IMA

## Project identity

This repository is for a prototype NPR 2.0-style FRTB IMA market-risk capital calculator.

The goal is not production regulatory compliance. The goal is to create a transparent, testable prototype that demonstrates how an existing risk engine could generate scenario P&L vectors while an ex-post capital layer assembles IMA-style capital.

## Regulatory caution

Treat all U.S. NPR 2.0 content as proposed-rule working assumptions. Do not present outputs as final regulatory capital.

Key prototype assumptions:
- Expected shortfall starts from 10-day scenario P&L vectors.
- Liquidity horizon adjustment is done from nested scenario vectors, not by scaling one final ES scalar.
- Risk factors classify as `MODELLABLE`, `TYPE_A_NMRF`, or `TYPE_B_NMRF`.
- Type A NMRFs go into both IMCC and SES.
- Type B NMRFs go into SES only with conservative aggregation.
- PLA uses a Kolmogorov-Smirnov statistic over HPL and RTPL vectors.
- Backtesting counts exceptions over 250 business days.

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
- Correct scenario-vector granularity.
- No inappropriate final-scalar liquidity-horizon scaling.
- Deterministic tests.
- Clear risk-factor classification logic.
- Separation of risk engine outputs from capital aggregation.
- Good documentation of assumptions and limitations.
