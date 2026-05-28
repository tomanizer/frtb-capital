# Capital Assembly

Capital assembly combines IMCC, SES, supervisory multiplier, and PLA add-on
inputs into the final IMA capital result for a desk.

## Boundary

- Owned by `frtb-ima`.
- Consumes package-internal calculation outputs and policy settings.
- Produces `CapitalComponents`, audit records, and desk eligibility signals.
- Does not aggregate SA components or firm-level totals; that belongs to
  `frtb-orchestration`.

## Evidence

- Package modules: `capital.py`, `audit.py`, `audit_inputs.py`, `logging.py`.
- Validation pack:
  [`VALIDATION_PACK.md`](../../../../packages/frtb-ima/docs/VALIDATION_PACK.md).
- Model derivation:
  [02_derivation.md](../model_documentation/02_derivation.md).
