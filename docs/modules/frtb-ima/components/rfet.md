# RFET

RFET classifies risk factors before IMA capital routing. The component records
observable-price evidence, data-pooling controls, representativeness checks,
exclusions, and Type A / Type B non-modellable risk-factor routing.

## Boundary

- Owned by `frtb-ima`.
- Consumes validated risk-factor evidence and policy thresholds.
- Produces RFET classifications and audit-grade evidence assessments.
- Does not source market data or decide firm-wide data-pooling policy.

## Evidence

- Package modules: `rfet.py`, `rfet_evidence.py`, `data_contracts.py`.
- Requirement registry:
  [`NPR_2_0_MARKET_RISK.yml`](../../../../packages/frtb-ima/docs/requirements/NPR_2_0_MARKET_RISK.yml).
- Traceability:
  [`REGULATORY_TRACEABILITY.md`](../../../../packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md).
