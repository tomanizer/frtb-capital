# AGENTS.md — frtb-sbm

`frtb-sbm` owns the Standardised Approach sensitivities-based method component.

## Current status

Phase 1 (#151) delivers cited GIRR delta/vega, FX delta, equity delta,
commodity delta, and CSR delta slices under BASEL_MAR21. Curvature inputs can be
validated row-wise via `validate_curvature_sensitivities` or through the GIRR
curvature Arrow/batch validation handoff; curvature capital remains explicitly
unsupported until #166.

`PACKAGE_METADATA.validation_status` is `PENDING`: fixture packs are synthetic
and do not constitute independent model validation. Do not treat outputs as
production regulatory capital.

Only `BASEL_MAR21` produces phase-1 capital. Other profile enum values
(`US_NPR_2_0`, `EU_CRR3`, `PRA_UK_CRR`) are accepted at the type level but fail
closed at runtime until cited reference data exists.

Package-local traceability lives under `packages/frtb-sbm/docs/`. See
`REGULATORY_TRACEABILITY.md` for implemented/unsupported status by area.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-drc`, `frtb-rrao`, or `frtb-cva`.
- Do not create a `frtb-sa` package; SA composition belongs in
  `frtb-orchestration`.
- Do not emit successful placeholder capital.
