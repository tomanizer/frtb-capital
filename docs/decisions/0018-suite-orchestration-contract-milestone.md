# 18. Suite orchestration contract milestone

Date: 2026-05-31

## Status

Accepted. The M1 milestone remains current, but the recognise-helper handoff
details in this ADR are superseded by
[ADR 0029](0029-unified-standardised-component-handoff-contract.md).

## Context

`frtb-orchestration` is intentionally partial, but the suite identity depends
on top-of-house aggregation across IMA, Standardised Approach components, and
CVA. Component packages expose deterministic public results with audit metadata.
Current orchestration validates shared SA handoffs and CVA result summaries, but
SA aggregation arithmetic and `calculate_suite_capital` still fail closed.

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
| SBM | `calculate_sbm_capital` result projected by `frtb-sbm.to_orchestration_handoff` to `frtb_common.ComponentResultHandoff` | Partial runtime; unsupported paths fail closed in component |
| DRC | `calculate_drc_capital` result projected by `frtb-drc.to_orchestration_handoff` to `frtb_common.ComponentResultHandoff` | Partial runtime; unsupported paths fail closed in component |
| RRAO | `calculate_rrao_capital` result projected by `frtb-rrao.to_orchestration_handoff` to `frtb_common.ComponentResultHandoff` | Implemented canonical-input path |
| CVA | `calculate_cva_capital` result summarized by `frtb_orchestration.recognise_cva_result` to `CvaResultHandoff` | Partial runtime; unsupported paths fail closed in component |

### M1 behaviour

- **SA composition** is `SBM + DRC + RRAO` with explicit subtotals and citations
  carried through `ComponentResultHandoff` records. The current runtime
  validates component slots and ADR 0022 jurisdiction-family consistency, then
  raises `NotImplementedCapitalComponentError` before aggregation arithmetic.
  No silent zero-capital substitution is allowed when a component raises
  unsupported-feature errors.
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

- Orchestration tests must cover SA handoff slot validation, jurisdiction-family
  guards, fail-closed aggregation paths, and each supported result-summary path.
- New SA component public results must add package-owned
  `to_orchestration_handoff` adapters before suite aggregation references them.
  Non-SA components may use structural result-summary handoffs until a shared
  contract is accepted.
- Package boundary discipline remains unchanged: `frtb-orchestration` may
  declare dependencies on multiple capital components, but runtime source should
  consume public handoff or summary contracts rather than importing sibling
  package internals.

## References

- [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`docs/decisions/0010-standardised-approach-component-taxonomy.md`](0010-standardised-approach-component-taxonomy.md)
- [`docs/decisions/0012-capital-impact-attribution.md`](0012-capital-impact-attribution.md)
- Issue [#230](https://github.com/tomanizer/frtb-capital/issues/230)
