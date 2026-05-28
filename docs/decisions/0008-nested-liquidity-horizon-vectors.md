# 8. Nested liquidity-horizon vectors for LHA ES

Date: 2026-05-28

## Status

Accepted

## Context

Liquidity-horizon adjusted ES must preserve scenario-level risk-factor
granularity. A scalar approximation that multiplies one final ES number by a
liquidity-horizon factor is easy to implement but loses the nested subset
structure required by the IMA calculation mechanics.

The migrated IMA package now has `ScenarioCube`, `lha_builder.py`, and
`scenario_validation.py` to construct and validate nested vectors from the
risk-factor axis.

## Decision

Use nested liquidity-horizon scenario vectors for LHA ES and IMCC:

- `LH10` contains all selected risk factors.
- `LH20` contains only risk factors with liquidity horizon at least 20 business
  days.
- `LH40`, `LH60`, and `LH120` follow the same nested subset rule.
- `LH10` is mandatory.
- LHA ES combines the ES of each nested vector with configured LHA weights.

The scalar helper in `liquidity_horizon.py` remains a labelled comparison path
for compatibility tests only. It must not be used for production-style capital
assembly.

Changing nested-vector construction, validation, horizon weights, or the
allowed use of scalar scaling is material under ADR 0005.

## Consequences

**Positive:**

- Scenario-level granularity is preserved through LHA ES and IMCC.
- Missing `LH10`, misaligned scenarios, and broken nesting evidence fail fast.
- The same construction supports all-class and per-risk-class IMCC inputs.

**Negative:**

- Callers must provide risk-factor definitions and scenario cubes with aligned
  axes.
- The package remains dependent on upstream systems for trade-to-risk-factor and
  risk-factor-to-liquidity-horizon assignment evidence.

## References

- `packages/frtb-ima/src/frtb_ima/lha_builder.py`.
- `packages/frtb-ima/src/frtb_ima/liquidity_horizon.py`.
- `packages/frtb-ima/src/frtb_ima/scenario_validation.py`.
- `packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md`.
- ADR 0005.
