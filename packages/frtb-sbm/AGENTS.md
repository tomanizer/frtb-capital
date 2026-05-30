# AGENTS.md — frtb-sbm

`frtb-sbm` owns the Standardised Approach sensitivities-based method component.

## Current status

Phase 1 (#151) delivers cited GIRR delta/vega, FX delta, equity delta, commodity
delta, and CSR non-sec delta slices under BASEL_MAR21. Curvature inputs can be
validated via `validate_curvature_sensitivities`; curvature capital remains
explicitly unsupported until #166.

Package-local traceability lives under `packages/frtb-sbm/docs/`. See
`REGULATORY_TRACEABILITY.md` for implemented/unsupported status by area.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-drc`, `frtb-rrao`, or `frtb-cva`.
- Do not create a `frtb-sa` package; SA composition belongs in
  `frtb-orchestration`.
- Do not emit successful placeholder capital.
