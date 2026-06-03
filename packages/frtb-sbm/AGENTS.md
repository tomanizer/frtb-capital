# AGENTS.md — frtb-sbm

Follow the suite-level portable worktree policy in
[`../../AGENTS.md`](../../AGENTS.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

`frtb-sbm` owns the Standardised Approach sensitivities-based method component.

## Current status

Phase 1 (#151) and follow-on vectorisation work deliver cited BASEL_MAR21
delta, vega, and curvature capital slices for GIRR, FX, equity, commodity, CSR
non-securitisation, CSR securitisation non-CTP, and CSR securitisation CTP.
Row-wise, package-owned batch, and Arrow batch entrypoints exist for these
supported paths; unsupported sub-features still fail closed.

`PACKAGE_METADATA.validation_status` is `PENDING`: fixture packs are synthetic
and do not constitute independent model validation. Do not treat outputs as
production regulatory capital.

`BASEL_MAR21` produces phase-1 capital for the supported delta, vega, and
curvature matrix. `US_NPR_2_0` produces capital only for GIRR delta; all other
U.S. NPR cells and the `EU_CRR3` / `PRA_UK_CRR` profiles fail closed until cited
reference data exists.

Package-local traceability lives under `packages/frtb-sbm/docs/`. See
`REGULATORY_TRACEABILITY.md` for implemented/unsupported status by area.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-drc`, `frtb-rrao`, or `frtb-cva`.
- Do not create a `frtb-sa` package; SA composition belongs in
  `frtb-orchestration`.
- Do not emit successful placeholder capital.
