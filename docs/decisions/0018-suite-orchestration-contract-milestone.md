# 18. Suite orchestration contract milestone

Date: 2026-05-31

## Status

Accepted

## Context

`frtb-orchestration` is intentionally partial, but the suite identity depends
on top-of-house aggregation across IMA, Standardised Approach components, and
CVA. Component packages already expose deterministic public results with audit
metadata. Orchestration today recognises those shapes and composes SA component
totals, but `calculate_suite_capital` still fails closed.

Without an explicit contract milestone, orchestration work risks ad hoc
integration or sibling-package imports that violate the monorepo boundary
rules.

## Decision

The next orchestration milestone is **M1: deterministic component handoff and SA
composition**. Firm-level `calculate_suite_capital` remains out of scope until
M2 after all required component result contracts and unsupported-path behaviour
are stable.

### M1 inputs

| Source | Contract | Notes |
| --- | --- | --- |
| IMA | `models_based_capital_for_policy` desk results + eligibility signal | Non-eligible desks route to SA fallback in M2 |
| SBM | `calculate_sbm_capital` result via `recognise_sbm_result` | Partial runtime; unsupported risk classes fail closed in component |
| DRC | `calculate_drc_capital` result via `recognise_drc_result` | Non-securitisation path only |
| RRAO | `calculate_rrao_capital` result via `recognise_rrao_result` | Implemented canonical-input path |
| CVA | `calculate_cva_capital` result handoff (to be added) | Partial runtime; unsupported methods fail closed in component |

### M1 behaviour

- **SA composition** is `SBM + DRC + RRAO` with explicit subtotals and citations
  carried through handoff records. No silent zero-capital substitution when a
  component raises unsupported-feature errors.
- **Unsupported component paths fail closed** at the component boundary.
  Orchestration does not catch and replace them with approximate totals.
- **Attribution / Euler decomposition** follows ADR 0012: exact Euler is valid
  only where branch metadata supports it; otherwise orchestration exposes
  residual or unsupported-method records rather than inventing contributions.
- **IMA fallback (M2)** will route non-IMA-eligible desks to the SA component
  stack using the same handoff contracts; M1 only requires eligibility signals
  to be preserved on IMA results.

### M2 (deferred)

- `calculate_suite_capital` end-to-end aggregation across IMA, SA, and CVA.
- Cross-component floors/add-ons and consolidated audit log emission.
- Explicit desk-level fallback routing tests.

## Consequences

- Orchestration tests must cover SA composition and each recognise/handoff path
  for supported component slices.
- New component public results must add a recognise helper before suite
  aggregation references them.
- Package boundary discipline remains unchanged: only `frtb-orchestration` may
  import multiple capital components.

## References

- [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`docs/decisions/0010-standardised-approach-component-taxonomy.md`](0010-standardised-approach-component-taxonomy.md)
- [`docs/decisions/0012-capital-impact-attribution.md`](0012-capital-impact-attribution.md)
- Issue [#230](https://github.com/tomanizer/frtb-capital/issues/230)
