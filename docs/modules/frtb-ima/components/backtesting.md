# Backtesting

Backtesting calculates exception counts and supervisory multiplier inputs used
by IMA desk eligibility and capital assembly.

## Boundary

- Owned by `frtb-ima`.
- Consumes aligned APL, HPL, and VaR observation vectors.
- Produces exception records and multiplier inputs.
- Does not own production P&L sourcing or firm-level breach governance.

## Evidence

- Public package module: `backtesting.py`.
- Physical implementation modules: focused `backtesting_*` modules.
- Model documentation:
  [Conceptual soundness](../model_documentation/01_conceptual_soundness.md)
  and [monitoring plan](../model_documentation/05_monitoring_plan.md).
- Traceability:
  [`REGULATORY_TRACEABILITY.md`](../../../../packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md).
