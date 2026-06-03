# frtb-orchestration

`frtb-orchestration` is the partial suite-level aggregation package.

## Package Status

- Package directory: `packages/frtb-orchestration`
- Import name: `frtb_orchestration`
- Implementation status: partial; SA arithmetic implemented, suite aggregation
  arithmetic not implemented
- Validation status: import smoke, explicit failure paths, SA component input_table
  composition tests, and fallback-routing tests

This is the only package allowed to depend on multiple capital component
packages. It owns the cross-component boundary and will own:

- composed SA capital from `frtb-sbm + frtb-drc + frtb-rrao`;
- IMA fallback routing when a desk is not model-eligible;
- top-of-the-house aggregation and cross-component reconciliation.

`calculate_suite_capital` raises an explicit unimplemented-component error until
top-of-the-house aggregation is implemented. SA composition consumes the shared
`frtb_common.ComponentCapitalSummary` contract: each SA component (`frtb-sbm`,
`frtb-drc`, `frtb-rrao`) projects its result via its own
`to_component_summary` adapter, and `compose_standardised_approach_capital`
validates the component slot, jurisdiction family, calculation date, and base
currency before returning the additive SA result `SBM + DRC + RRAO`.
`ima_desk_eligibility` can carry structural IMA eligibility strings or string
enums; desks marked `SA_FALLBACK` are recorded as routed to the Standardised
Approach stack. Orchestration consumes only the typed summaries and input table
routes; there is no reach into raw component result
internals. Runtime code must not import sibling capital packages; package-local
tests use concrete DRC/RRAO fixtures only to verify the adapters remain
compatible with public component outputs. See ADR 0029.

CVA is separate from SA composition. The current `recognise_cva_summary` helper
projects a public CVA capital result into `CvaCapitalSummary` with method,
BA-CVA/SA-CVA totals where present, lineage hashes, counts, citations, and
warnings. That summary is preparatory evidence for top-of-the-house aggregation;
it does not make `calculate_suite_capital` available.

## Arrow Boundary

Orchestration may accept Arrow-backed data at suite input boundaries before data
is routed to component-owned public adapters. Once a component has calculated
capital, orchestration consumes public audited result or summary shapes only,
such as `ComponentCapitalSummary`, `CvaCapitalSummary`, and future IMA
result/eligibility summaries. It must not import or coordinate private package
batch modules, because those batches are package kernel internals rather than
suite contracts.

IMA scenario cubes remain NumPy-native inside `frtb-ima`; orchestration should
route IMA eligibility and result summaries, not scenario-cube internals. SA
component Arrow input tables are owned by their packages, and orchestration should
not bypass their validation or batch builders.
