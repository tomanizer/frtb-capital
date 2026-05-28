# 9. Desk eligibility as a two-state capital guard

Date: 2026-05-28

## Status

Accepted

## Context

Desk eligibility affects whether a desk may receive IMA capital treatment. A
full production lifecycle would include approval, loss of eligibility,
remediation, re-entry, supervisory overrides, and fallback capital. That
lifecycle is broader than the current `frtb-ima` package boundary.

The package still needs a hard guard so models-based capital is not assembled
for a desk that the caller has classified as requiring standardized fallback.

## Decision

Represent eligibility at the package boundary with the two-state
`DeskEligibilityStatus` enum:

- `IMA_ELIGIBLE`
- `SA_FALLBACK`

`desk_eligibility_from_results` maps PLA and backtesting diagnostics to the
two-state guard for the prototype path. `models_based_capital_for_policy`
rejects `SA_FALLBACK` desks. The package does not implement the full lifecycle
state machine, remediation workflow, supervisory approval process, or SA
fallback calculation.

Changing eligibility states, guard semantics, lifecycle scope, or fallback
capital ownership is material under ADR 0005.

## Consequences

**Positive:**

- The package fails hard before calculating IMA capital for fallback desks.
- The IMA model boundary stays focused on desk-level model-eligible capital.
- Full eligibility lifecycle work can be added later without hiding it inside
  capital assembly.

**Negative:**

- The two-state guard is not sufficient for production desk lifecycle
  governance.
- Orchestration and SA packages must own fallback capital once implemented.

## References

- `packages/frtb-ima/src/frtb_ima/regimes.py`.
- `packages/frtb-ima/src/frtb_ima/capital.py`.
- `packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md`.
- `packages/frtb-ima/docs/requirements/NPR_2_0_MARKET_RISK.yml`.
- ADR 0005.
