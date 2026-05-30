# CLAUDE.md — frtb-sbm

Review `frtb-sbm` as the owner of SBM capital only.

## Current implementation (BASEL_MAR21 phase 1)

| Risk class | Delta | Vega | Curvature |
| --- | --- | --- | --- |
| GIRR | Implemented | Implemented | Contracts only (#165); capital unsupported (#166) |
| FX | Implemented | Unsupported | Unsupported |
| Equity | Implemented | Unsupported | Unsupported |
| Commodity | Implemented | Unsupported | Unsupported |
| CSR non-securitisation | Implemented | Unsupported | Unsupported |
| CSR securitisation CTP / non-CTP | Unsupported | Unsupported | Unsupported |

Public entry point: `calculate_sbm_capital`. Supported paths return cited
`SbmCapitalResult` records with audit hashes and scenario evidence. All other
profile/risk-class/measure combinations fail closed with
`UnsupportedRegulatoryFeatureError` or `SbmInputError` — never silent
zero-capital placeholders.

Curvature up/down shock inputs may be validated with
`validate_curvature_sensitivities`; curvature capital remains explicitly
unsupported until the aggregation path in #166 lands.

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
- `numpy` is the only runtime numerical dependency for calculation kernels.
- Package-local traceability: `packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md`.

## Profile boundaries

`SbmRegulatoryProfile` includes `US_NPR_2_0`, `EU_CRR3`, and `PRA_UK_CRR` for
forward compatibility, but phase-1 capital is implemented only for
`BASEL_MAR21`. Non-Basel profiles fail closed at validation with explicit
unsupported-profile errors.
