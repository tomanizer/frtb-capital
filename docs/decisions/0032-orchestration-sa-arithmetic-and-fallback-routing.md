# 32. Orchestration SA arithmetic and fallback route recording

Date: 2026-06-02

## Status

Accepted

## Context

ADR 0010 defines the Standardised Approach as the composed total
`SBM + DRC + RRAO`. ADR 0029 moved the component handoff contract to
`frtb_common.ComponentResultHandoff` and left
`compose_standardised_approach_capital` failing closed before arithmetic.

Issue #408 implements that arithmetic and the first desk-level IMA fallback
route recording at the orchestration boundary.

## Decision

`frtb-orchestration` composes SA capital from the three shared handoffs:

```text
SA capital = SBM capital + DRC capital + RRAO capital
```

Before addition, orchestration validates:

- every handoff is in its expected SBM, DRC, or RRAO component slot;
- all component profile IDs map to one ADR 0022 jurisdiction family;
- all components share one calculation date;
- all components share one base currency;
- every component total is non-negative.

The result is a frozen `StandardisedApproachCapitalResult` with the composed
total, component subtotals, jurisdiction family, unique component citations,
warnings, and optional fallback routes.

IMA fallback route recording remains structural. Runtime orchestration does not
import `frtb_ima`; callers may provide `ima_desk_eligibility` as a desk-id to
status mapping using strings or string enums. Desks marked `SA_FALLBACK` are
recorded as routed to `STANDARDISED_APPROACH` with reason code
`ima_desk_not_model_eligible`. Desks marked `IMA_ELIGIBLE` are not routed.
Unknown eligibility statuses fail closed.

Top-of-house `calculate_suite_capital` is implemented in
[ADR 0039](0039-orchestration-suite-capital-aggregation.md). This ADR does not
define that aggregation step.

## Consequences

- SA composition is now capital-producing when all three component handoffs are
  supplied for a consistent jurisdiction family, date, and base currency.
- Unsupported component paths still fail closed inside the owning component;
  orchestration does not substitute zeros or approximations.
- Fallback routing is audit-visible but does not calculate component-level desk
  inputs. Component packages still own their canonical SBM, DRC, and RRAO
  calculations.
- ADR 0018 and ADR 0029 remain valid for handoff boundaries, but their
  statements that SA arithmetic is unavailable are superseded by this ADR.

## References

- ADR 0010: Standardised Approach component taxonomy.
- ADR 0018: Suite orchestration contract milestone.
- ADR 0022: SA jurisdiction profile consistency guard.
- ADR 0029: Unified standardised-component orchestration handoff contract.
- GitHub issue #408.
