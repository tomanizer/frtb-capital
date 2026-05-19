# Codex handoff summary

## One-line task

Build a first Python prototype of an NPR 2.0-style FRTB IMA capital calculator for `tomanizer/FRTB-IMA`.

## Architecture

```text
Existing risk engine
    -> 10-day scenario P&L vectors
    -> ex-post capital aggregation layer
    -> desk-level dashboard
```

## First milestone

Deliver a working demo that computes:

- risk-factor modellability classification,
- liquidity horizon adjusted expected shortfall,
- IMCC,
- SES,
- models-based capital,
- PLA KS statistic,
- backtesting exception counts.

## Build sequence

1. Bootstrap package, pyproject, tests.
2. Add data models.
3. Add expected shortfall.
4. Add liquidity horizon adjustment from nested vectors.
5. Add RFET / modellability classifier.
6. Add Type A / Type B NMRF SES prototype.
7. Add IMCC aggregation.
8. Add PLA KS and backtesting.
9. Add capital assembly.
10. Add synthetic demo.

## Key warning

Do not calculate liquidity horizon adjustment by taking one final ES number and multiplying by a square-root factor. The prototype should use scenario vectors by nested liquidity-horizon subsets.
