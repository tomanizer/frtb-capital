# AGENTS.md — frtb-orchestration

`frtb-orchestration` owns suite-level aggregation and routing.

## Current status

The package has partial handoff and guard contracts:

- SA composition consumes `frtb_common.ComponentResultHandoff` from package-owned
  SBM, DRC, and RRAO adapters, validates component slots and jurisdiction
  families, then fails closed before aggregation arithmetic.
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
