# CLAUDE.md — frtb-sbm

Review `frtb-sbm` as the owner of SBM capital only.

## Current implementation (BASEL_MAR21 phase 1)

| Risk class | Delta | Vega | Curvature |
| --- | --- | --- | --- |
| GIRR | Implemented | Implemented | Implemented row-wise |
| FX | Implemented | Unsupported | Implemented row-wise |
| Equity | Implemented | Unsupported | Implemented row-wise for spot; repo curvature unsupported |
| Commodity | Implemented | Unsupported | Implemented row-wise |
| CSR non-securitisation | Implemented | Unsupported | Implemented row-wise |
| CSR securitisation CTP / non-CTP | Implemented | Unsupported | Implemented row-wise |

Public entry point: `calculate_sbm_capital`. Supported paths return cited
`SbmCapitalResult` records with audit hashes and scenario evidence. All other
profile/risk-class/measure combinations fail closed with
`UnsupportedRegulatoryFeatureError` or `SbmInputError` — never silent
zero-capital placeholders.

Curvature up/down shock inputs may be validated with
`validate_curvature_sensitivities`. Public curvature capital is available
through the row API; the GIRR Arrow/batch curvature handoff remains
validation-only until high-volume curvature batches are implemented.

## Validation and deployment readiness

`PACKAGE_METADATA.validation_status` is `ValidationStatus.PENDING`. The package
self-declares as not independently validated. Synthetic fixture packs prove
internal consistency only; they are not Basel QIS or other external regulatory
vectors. Do not clear `PENDING` without a genuine model-validation exercise.

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

`SbmRegulatoryProfile` includes `US_NPR_2_0`, `EU_CRR3`, and `PRA_UK_CRR` for
forward compatibility, but phase-1 capital is implemented only for
`BASEL_MAR21`. Non-Basel profiles fail closed at validation with explicit
unsupported-profile errors.
