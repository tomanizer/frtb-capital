# CLAUDE.md — frtb-sbm

Follow the suite-level portable worktree policy in
[`../../CLAUDE.md`](../../CLAUDE.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

Review `frtb-sbm` as the owner of SBM capital only.

## Current implementation (BASEL_MAR21 phase 1)

| Risk class | Delta | Vega | Curvature |
| --- | --- | --- | --- |
| GIRR | Implemented under audit | Implemented under audit | Implemented under audit |
| FX | Implemented under audit | Implemented under audit | Implemented under audit |
| Equity | Implemented under audit | Implemented under audit | Implemented under audit; repo sub-features fail closed |
| Commodity | Implemented under audit | Implemented under audit | Implemented under audit |
| CSR non-securitisation | Implemented under audit | Implemented under audit | Implemented under audit |
| CSR securitisation non-CTP / CTP | Implemented under audit | Implemented under audit | Implemented under audit |

Public entry point: `calculate_sbm_capital`. Supported paths return cited
`SbmCapitalResult` records with audit hashes and scenario evidence. All other
profile/risk-class/measure combinations fail closed with
`UnsupportedRegulatoryFeatureError` or `SbmInputError` — never silent
zero-capital placeholders.

Curvature up/down shock inputs may be validated with
`validate_curvature_sensitivities`. Public curvature capital is available
through row-wise, package-owned batch, and Arrow batch entrypoints for all
supported BASEL_MAR21 risk classes.

## Validation and deployment readiness

`PACKAGE_METADATA.validation_status` is `ValidationStatus.PENDING`. The package
self-declares as not independently validated. Synthetic fixture packs prove
internal consistency only; they are not Basel QIS or other external regulatory
vectors. Do not clear `PENDING` without a genuine model-validation exercise.

## ADR 0045 target layout

Epic [#725](https://github.com/tomanizer/frtb-capital/issues/725) tracks the
[`ADR 0045`](../../docs/decisions/0045-canonical-batch-pipeline-with-adapter-ingress.md)
canonical batch pipeline consolidation. Review SBM refactors toward this layout:

```text
adapters/ -> validation/ -> kernel/ -> assembly/ -> registry.py
```

Adapters own Arrow, CRIF, row, and column ingress into the package-owned SBM
batch; validation modules own package-local input rules and public errors;
kernels own cited regulatory math and must not import Arrow or dataframes;
assembly owns result records, hashes, citations, and audit payloads; and
`registry.py` owns risk-class and measure dispatch instead of wrapper matrices.

Reject empty stage packages that shadow existing modules. Use
[`stage_module_skeletons.md`](../../docs/quality/stage_module_skeletons.md) as
the import-shadowing guardrail before adding `adapters/`, `validation/`,
`kernel/`, or `assembly/`.

## Engineering rules

- Reject sibling capital-package imports; shared abstractions belong in
  `frtb-common`.
- Reject regulatory thresholds without precise paragraph citations.
- Do not emit successful placeholder capital for unsupported paths.
- `numpy` is the runtime numerical dependency for calculation kernels. Arrow is
  allowed only in package adapters, CRIF normalization, and handoff modules
  under suite ADR 0023; kernels must not import `pyarrow`, `pandas`, or
  `polars`.
- Package-local traceability: `packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md`.

## Profile boundaries

`SbmRegulatoryProfile` includes `US_NPR_2_0`, `EU_CRR3`, and `PRA_UK_CRR`.
`US_NPR_2_0` is capital-producing for GIRR delta/vega/curvature,
reporting-currency FX delta/vega/curvature, equity delta, and commodity delta
as proposed-rule comparison material. `EU_CRR3` is partially runtime-supported
for selected delta, vega, and curvature slices with explicit citations.
`PRA_UK_CRR` is runtime-supported for GIRR delta/vega/curvature,
reporting-currency FX delta/vega/curvature, equity delta, and commodity delta,
with PS1/26 Appendix 1 / PRA2026/1 citation ids and deterministic fixtures. Do
not open another PRA runtime gate without exact-cell PRA citations,
profile-owned reference data, and deterministic fixtures.
