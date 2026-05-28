# Expected Shortfall And IMCC

This component computes empirical expected shortfall, liquidity-horizon adjusted
expected shortfall, reduced-set expected shortfall, and the IMCC capital term.

## Boundary

- Owned by `frtb-ima`.
- Consumes scenario vectors, liquidity-horizon metadata, risk-class mappings,
  and policy parameters.
- Produces ES, LHA ES, reduced-set ES, and IMCC outputs with deterministic
  audit fields.
- Does not generate scenarios or perform product valuation.

## Evidence

- Package modules: `expected_shortfall.py`, `liquidity_horizon.py`,
  `lha_builder.py`, `imcc.py`, `reduced_set.py`, `scenario_validation.py`.
- Model derivation:
  [02_derivation.md](../model_documentation/02_derivation.md).
- Traceability:
  [`REGULATORY_TRACEABILITY.md`](../../../../packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md).
