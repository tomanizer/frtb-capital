# AGENTS.md — frtb-orchestration

`frtb-orchestration` owns suite-level aggregation and routing.

## Current status

The package has partial orchestration contracts:

- SA composition consumes `frtb_common.ComponentCapitalSummary` from package-owned
  SBM, DRC, and RRAO adapters, validates component slots and jurisdiction
  families plus run-context consistency, and returns the additive
  `SBM + DRC + RRAO` result.
- IMA fallback route recording accepts structural desk eligibility signals and
  records `SA_FALLBACK` desks as routed to the Standardised Approach stack.
- CVA has a structural `CvaResultHandoff` projection for future top-of-house
  aggregation.
- `calculate_suite_capital` still fails explicitly until full suite aggregation
  lands.

## Rules

- May declare dependencies on `frtb-common` and capital component packages, but
  runtime source must not import sibling capital packages unless a future ADR
  changes the boundary.
- Owns SA composition from `frtb-sbm + frtb-drc + frtb-rrao`.
- Owns fallback routing when IMA eligibility fails.
- Do not emit successful placeholder capital.
- Do not reach into private component batch modules; consume public handoff or
  result-summary contracts only.
