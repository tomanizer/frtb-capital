# Assumptions And Limitations

## Risk-Class Scope Matrix

`BASEL_MAR21` is the canonical capital-producing profile. `US_NPR_2_0` has
GIRR delta, GIRR vega, GIRR curvature, reporting-currency FX delta, FX vega,
FX curvature, equity delta, and commodity delta comparison cells.
`PRA_UK_CRR` has GIRR delta only. `EU_CRR3` remains runtime fail-closed, and
every PRA cell outside GIRR delta remains fail-closed.

| Risk class | Delta | Vega | Curvature | Notes |
| --- | --- | --- | --- | --- |
| GIRR | Supported under MAR21.40-MAR21.42 | Supported under MAR21.90-MAR21.95 | Supported under MAR21.5 and MAR21.96-MAR21.101 | Requires cited tenor and bucket metadata. |
| FX | Supported under MAR21.86-MAR21.89 | Supported under MAR21.90-MAR21.95 | Supported with explicit MAR21.98 scalar evidence where required | Reporting-currency and specified-pair treatment are validated. |
| Equity | Supported under MAR21.71-MAR21.80 | Supported under MAR21.90-MAR21.95 | Supported except unsupported repo sub-features | Repo vega/curvature gaps fail closed. |
| Commodity | Supported under MAR21.81-MAR21.85 | Supported under MAR21.90-MAR21.95 | Supported under MAR21.96-MAR21.101 | Location and tenor metadata drive correlations. |
| CSR non-securitisation | Supported under MAR21.51-MAR21.57 | Supported under MAR21.90-MAR21.95 | Supported under MAR21.96-MAR21.101 | Bond/CDS basis is validated. |
| CSR securitisation non-CTP | Supported under MAR21.61-MAR21.70 | Supported under MAR21.90-MAR21.95 | Supported under MAR21.96-MAR21.101 | Cited reference tables are present; unsupported profiles fail closed. |
| CSR securitisation CTP | Supported under MAR21.58-MAR21.65 | Supported under MAR21.90-MAR21.95 | Supported under MAR21.96-MAR21.101 | Missing decomposition evidence fails closed. |

## Unsupported Scope

Unsupported paths raise `UnsupportedRegulatoryFeatureError` or `SbmInputError`
before capital is emitted:

- `US_NPR_2_0` runtime profile cells outside GIRR delta, GIRR vega, GIRR curvature, FX delta, FX vega, FX curvature, equity delta, and commodity delta;
- `US_NPR_2_0` FX base-currency treatment, which remains unsupported until
  prior-supervisory-approval and translation-risk evidence are represented
  explicitly in runtime controls and fixtures;
- `EU_CRR3` runtime profile cells;
- `PRA_UK_CRR` runtime profile cells outside GIRR delta;
- risk-class/measure combinations outside the supported matrix;
- missing curvature up/down shock inputs;
- missing FX curvature scalar evidence where MAR21.98 requires it;
- equity repo vega/curvature sub-features.

## Attribution And Impact Limits

Analytical Euler attribution is implemented for selected, differentiable delta
and vega branches when scenario detail and full pairwise correlation evidence are
retained. Curvature, active floors, alternative `S_b`, missing scenario detail,
and incomplete pairwise evidence return explicit unsupported residual records
rather than derivative estimates. Finite-difference impact is supported only as
baseline-vs-candidate capital comparison and is not a marginal contribution.

## Validation Limits

Evidence is synthetic and deterministic. It supports engineering review and
model-validation planning, but it does not prove bank source-data controls,
legal interpretation, supervisory acceptance, or final regulatory capital.
