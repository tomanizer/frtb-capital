# Codex handoff summary

## One-line task

Maintain a transparent Python prototype of an NPR 2.0-style FRTB IMA capital
assembly layer for `tomanizer/FRTB-IMA`.

## Architecture

```text
Existing risk engine
    -> RFET classifications known before valuation
    -> NMRF method-selection evidence, instructions, and valuation specs
    -> 10-day scenario P&L vectors and NMRF stress artifacts
    -> ex-post capital aggregation layer
    -> structured JSON runtime logs and NDJSON desk audit records
```

## Current implemented milestone

The current demo computes:

- risk-factor modellability classification,
- liquidity horizon adjusted expected shortfall,
- IMCC,
- NMRF method evidence, valuation specs, and stress-artifact validation,
- SES,
- models-based capital,
- PLA KS statistic,
- backtesting exception counts,
- structured logging and desk-level audit records.

The package still does not generate market data, choose stress periods, price
trades, implement DRC/standardized capital, or produce a final regulatory
submission package.

## Build sequence completed

1. Bootstrap package, pyproject, tests.
2. Add data models.
3. Add expected shortfall.
4. Add liquidity horizon adjustment from nested vectors.
5. Add RFET / modellability classifier.
6. Add Type A / Type B NMRF SES aggregation.
7. Add NMRF method selection, valuation instructions/specs, valuation-run reconciliation, and stress artifacts.
8. Add IMCC aggregation.
9. Add PLA KS and backtesting.
10. Add capital assembly.
11. Add synthetic demo.
12. Add structured logging and NDJSON audit records.

## Current next workstreams

1. Risk-factor to liquidity-horizon mapping table and evidence.
2. Stress-period selection/calibration interface.
3. Reduced risk-factor set construction and governance evidence.
4. Institutional NMRF pricing/revaluation adapter beyond the current handoff reconciliation.
5. EU/PRA Spearman PLA and jurisdiction-specific source mapping.
6. DRC, standardized/fallback capital, and legal-entity consolidation.
7. Full run report generation and orchestration-layer storage/telemetry sinks.

## Key warning

Do not calculate liquidity horizon adjustment by taking one final ES number and multiplying by a square-root factor. The prototype should use scenario vectors by nested liquidity-horizon subsets.
