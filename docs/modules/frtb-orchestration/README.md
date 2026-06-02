# frtb-orchestration

`frtb-orchestration` is the partial suite-level aggregation package.

## Package Status

- Package directory: `packages/frtb-orchestration`
- Import name: `frtb_orchestration`
- Implementation status: partial; suite aggregation arithmetic not implemented
- Validation status: import smoke, explicit failure paths, and SA component
  handoff composition tests

This is the only package allowed to depend on multiple capital component
packages. It owns the cross-component boundary and will own:

- composed SA capital from `frtb-sbm + frtb-drc + frtb-rrao`;
- IMA fallback routing when a desk is not model-eligible;
- top-of-the-house aggregation and cross-component reconciliation.

`calculate_suite_capital` raises an explicit unimplemented-component error until
top-of-the-house aggregation is implemented. SA composition consumes the shared
`frtb_common.ComponentResultHandoff` contract: each SA component (`frtb-sbm`,
`frtb-drc`, `frtb-rrao`) projects its result via its own
`to_orchestration_handoff` adapter, and `compose_standardised_approach_capital`
validates the component slot and jurisdiction family before failing closed ahead
of SA aggregation arithmetic. Orchestration consumes only the typed handoff —
there are no duck-typing `recognise_*` helpers and no reach into raw component
result internals. Runtime code must not import sibling capital packages;
package-local tests use concrete DRC/RRAO fixtures only to verify the adapters
remain compatible with public component outputs. See ADR 0029.

## Arrow Boundary

Orchestration may accept Arrow-backed data at suite input boundaries before data
is routed to component-owned public adapters. Once a component has calculated
capital, orchestration consumes public audited result shapes only, such as DRC,
RRAO, SBM, CVA, and IMA result/eligibility summaries. It must not import or
coordinate private package batch modules, because those batches are package
kernel internals rather than suite contracts.

IMA scenario cubes remain NumPy-native inside `frtb-ima`; orchestration should
route IMA eligibility and result summaries, not scenario-cube internals. SA
component Arrow handoffs are owned by their packages, and orchestration should
not bypass their validation or batch builders.
