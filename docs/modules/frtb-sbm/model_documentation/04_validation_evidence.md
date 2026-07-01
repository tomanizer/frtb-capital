# Validation Evidence

## Fixture Evidence

| Fixture or test | Scope | Evidence |
| --- | --- | --- |
| `fixtures/girr_delta_v1/` | GIRR delta | MAR21.40 risk weights, MAR21.41 intra-bucket, MAR21.42 inter-bucket, MAR21.6-MAR21.7 scenario selection. |
| `fixtures/girr_vega_v1/` | GIRR vega | MAR21.92-MAR21.95 vega scaling and aggregation. |
| `fixtures/girr_delta_us_npr_v1/` | U.S. NPR 2.0 GIRR delta | Federal Register 91 FR 15020 section V.A.7.a profile-owned GIRR delta citations, profile hash, and fail-closed comparison-profile behavior. |
| `fixtures/girr_vega_us_npr_v1/` | U.S. NPR 2.0 GIRR vega | Federal Register 91 FR 15020 section V.A.7.a profile-owned GIRR vega citations, row/batch/Arrow parity, and fail-closed remaining-cell behavior. |
| `fixtures/girr_curvature_us_npr_v1/` | U.S. NPR 2.0 GIRR curvature | Federal Register 91 FR 15037-15038 section V.A.7.a profile-owned GIRR curvature citations, CVR branch records, row/batch/Arrow parity, and fail-closed remaining-cell behavior. |
| `fixtures/fx_delta_us_npr_v1/` | U.S. NPR 2.0 FX delta | Federal Register 91 FR 15020 section V.A.7.a profile-owned FX delta citations, reporting-currency basis, row/batch/Arrow parity, and fail-closed base-currency behavior. |
| `fixtures/fx_vega_us_npr_v1/` | U.S. NPR 2.0 FX vega | Federal Register 91 FR 15020 section V.A.7.a profile-owned FX vega citations, reporting-currency basis, row/batch/Arrow parity, and no Basel citation leakage. |
| `fixtures/fx_curvature_us_npr_v1/` | U.S. NPR 2.0 FX curvature | Federal Register 91 FR 15037-15038 section V.A.7.a profile-owned FX curvature citations, CVR branch records, row/batch/Arrow parity, and no Basel citation leakage. |
| `fixtures/fx_delta_v1/` | FX delta | MAR21.86-MAR21.89 bucket, risk-weight, specified-pair, and inter-bucket behavior. |
| `fixtures/equity_delta_v1/` | Equity delta | MAR21.72, MAR21.77-MAR21.80 bucket and correlation behavior. |
| `fixtures/commodity_delta_v1/` | Commodity delta | MAR21.81-MAR21.85 bucket and correlation behavior. |
| `fixtures/csr_nonsec_delta_v1/` | CSR non-securitisation delta | MAR21.51-MAR21.57 bucket, risk-weight, basis, and scenario behavior. |

## Unit, Batch, And Handoff Evidence

- `tests/risk_classes/` covers supported delta/vega risk-class paths and
  class-specific fail-closed cases.
- `test_curvature.py` covers curvature branch selection, floors, and unsupported
  curvature sub-features.
- `test_sbm_*_batch*.py` and `test_sbm_*_arrow*.py` check row/batch/Arrow parity
  for supported paths.
- `test_sbm_fixture_workflow.py`, `test_sbm_audit.py`, and `test_sbm_replay.py`
  cover deterministic fixture replay and audit records.
- `test_sbm_unsupported_features.py`, `test_sbm_support_matrix.py`, and
  `test_sbm_attribution_impact.py` cover explicit unsupported behavior,
  analytical Euler attribution reconciliation, and finite-difference impact.

## Benchmark Evidence

`test_sbm_benchmark.py` and the benchmark artifacts referenced in
`docs/quality/benchmark_budgets.toml` provide reportable performance sentinels
for implemented batch and Arrow paths. They are not substitutes for independent
model validation.
