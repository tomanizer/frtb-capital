# PLA

PLA calculates profit-and-loss attribution diagnostics used for IMA desk
eligibility. It remains an IMA internal component, not a separate capital
package.

## Boundary

- Owned by `frtb-ima`.
- Consumes aligned HPL and RTPL observations plus regime policy.
- Produces PLA metrics, traffic-light zone, and add-on inputs where applicable.
- Does not own valuation explain, P&L production, or business-calendar
  governance outside the package contracts.

## Evidence

- Package modules: `pla.py`, `regimes.py`.
- Tests: `tests/test_pla.py`, `tests/test_properties_pla.py`.
- Traceability:
  [`REGULATORY_TRACEABILITY.md`](../../../../packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md).
