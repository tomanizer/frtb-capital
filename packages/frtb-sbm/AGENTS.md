# AGENTS.md — frtb-sbm

`frtb-sbm` owns the Standardised Approach sensitivities-based method component.

## Current status

The package is scaffolded only. It must fail explicitly for calculation entry
points until canonical sensitivity contracts and cited vertical slices are
implemented.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-drc`, `frtb-rrao`, or `frtb-cva`.
- Do not create a `frtb-sa` package; SA composition belongs in
  `frtb-orchestration`.
- Do not emit successful placeholder capital.
