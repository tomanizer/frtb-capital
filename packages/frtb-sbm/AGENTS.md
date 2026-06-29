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
curvature matrix with per-risk-class fixture packs. `US_NPR_2_0`, `EU_CRR3`, and
`PRA_UK_CRR` are comparison-slice profiles: all 21 runtime gates are open with
Basel-mirrored numerics and profile-owned citation ids, but only GIRR delta has
a deterministic fixture per profile. Comparison-slice outputs are not final
regulatory capital.

Package-local traceability lives under `packages/frtb-sbm/docs/`. See
`REGULATORY_TRACEABILITY.md` for implemented/unsupported status by area.

## ADR 0045 target layout

Epic [#725](https://github.com/tomanizer/frtb-capital/issues/725) tracks the
[`ADR 0045`](../../docs/decisions/0045-canonical-batch-pipeline-with-adapter-ingress.md)
canonical batch pipeline consolidation. The intended end state for SBM runtime
code is:

```text
adapters/ -> validation/ -> kernel/ -> assembly/ -> registry.py
```

Use adapters for Arrow, CRIF, row, and column ingress into the package-owned SBM
batch; keep validation rules out of kernels; keep regulatory math in kernel
modules without Arrow/dataframe imports; assemble citations, hashes, audit, and
public result records after the kernel; and use `registry.py` for risk-class and
measure dispatch instead of wrapper matrices.

Do not add empty stage packages that shadow existing modules. Follow
[`stage_module_skeletons.md`](../../docs/quality/stage_module_skeletons.md) when
introducing `adapters/`, `validation/`, `kernel/`, or `assembly/`.

## Rules

- May depend on `frtb-common`.
- Must not import from `frtb-ima`, `frtb-drc`, `frtb-rrao`, or `frtb-cva`.
- Do not create a `frtb-sa` package; SA composition belongs in
  `frtb-orchestration`.
- Do not emit successful placeholder capital.
