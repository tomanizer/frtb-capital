# Stress-Period Selection

Stress-period selection controls the windows and stress artifacts used by IMA
expected shortfall and NMRF stress-scenario calculations.

## Boundary

- Owned by `frtb-ima`.
- Validates supplied stress-period metadata and stress artifacts.
- Keeps stress-window evidence explicit for audit and validation review.
- Does not source historical market data or run upstream pricing engines.

## Evidence

- Package modules: `stress_periods.py`, `nmrf_stress_spec.py`,
  `nmrf_valuation_run.py`.
- Validation notebooks:
  [`packages/frtb-ima/notebooks/`](../../../../packages/frtb-ima/notebooks/).
- Traceability:
  [`REGULATORY_TRACEABILITY.md`](../../../../packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md).
