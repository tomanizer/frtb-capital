# Codex handoff summary

## One-line task

Maintain a transparent Python prototype of an NPR 2.0-style FRTB IMA capital
assembly layer for `tomanizer/FRTB-IMA`.

## Architecture

```text
Existing risk engine
    -> RFET classifications known before valuation
    -> supplied historical risk-class loss series for stress-period selection
    -> upstream IMCC stressed-ES scenario preparation informed by selections
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
- stress-period selection from supplied historical risk-class loss vectors,
- NMRF method evidence, valuation specs, and stress-artifact validation,
- SES,
- models-based capital,
- PLA KS statistic,
- backtesting exception counts,
- structured logging and desk-level audit records.

The package still does not source raw market data, price trades, implement
DRC/standardized capital, or produce a final regulatory submission package.
Stress-period selections directly feed NMRF valuation specs and separately
inform upstream IMCC scenario preparation; `imcc.py` consumes numeric ES values,
not stress-period objects.

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
13. Add vectorized stress-period selection from supplied historical loss series.
14. Add deterministic Markdown audit report rendering and `make audit`.
15. Add risk-factor category to liquidity-horizon mapping table helpers.

## Current next workstreams

1. Liquidity-horizon category assignment evidence from proprietary instrument/vendor data.
2. Reduced risk-factor set construction and governance evidence.
3. Institutional NMRF pricing/revaluation adapter beyond the current handoff reconciliation.
4. Raw market-data calibration adapters and formal stress-period governance evidence.
5. EU/PRA Spearman PLA and jurisdiction-specific source mapping.
6. DRC, standardized/fallback capital, and legal-entity consolidation.
7. Regulatory disclosure templates and orchestration-layer storage/telemetry sinks.

## Key warning

Do not calculate liquidity horizon adjustment by taking one final ES number and multiplying by a square-root factor. The prototype should use scenario vectors by nested liquidity-horizon subsets.
