# NMRF And SES

The NMRF and SES component routes non-modellable risk factors and calculates
stress-scenario capital contributions.

## Boundary

- Owned by `frtb-ima`.
- Consumes RFET classifications, NMRF method selections, valuation-run evidence,
  and stress specifications.
- Produces SES contributions and aggregation evidence for capital assembly.
- Does not decide market-data sourcing controls or upstream valuation models.

## Evidence

- Package modules: `nmrf.py`, `nmrf_method_selection.py`,
  `nmrf_stress_spec.py`, `nmrf_valuation_run.py`.
- Model documentation:
  [Conceptual soundness](../model_documentation/01_conceptual_soundness.md)
  and [derivation](../model_documentation/02_derivation.md).
- Traceability:
  [`REGULATORY_TRACEABILITY.md`](../../../../packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md).
