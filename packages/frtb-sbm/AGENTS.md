# AGENTS.md — frtb-sbm

`frtb-sbm` owns the Standardised Approach sensitivities-based method component.

## Current status

The package is scaffolded. Phase 1 (#151) adds a cited GIRR delta vertical
slice in dependency order (#152–#159). Until the public API wiring issue lands,
calculation entry points must fail explicitly.

Package-local traceability lives under `packages/frtb-sbm/docs/`. See
`REGULATORY_TRACEABILITY.md` for scaffold/planned/partial/implemented/unsupported
status by area.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-drc`, `frtb-rrao`, or `frtb-cva`.
- Do not create a `frtb-sa` package; SA composition belongs in
  `frtb-orchestration`.
- Do not emit successful placeholder capital.
