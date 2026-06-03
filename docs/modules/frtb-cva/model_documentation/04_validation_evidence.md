# Validation Evidence

## Fixture Evidence

| Fixture or test | Scope | Evidence |
| --- | --- | --- |
| `packages/frtb-cva/tests/fixtures/ba_cva_reduced_v1/` | Reduced BA-CVA | Synthetic cases, expected outputs, and deterministic replay. |
| `packages/frtb-cva/tests/fixtures/sa_cva_girr_delta_v1/` | SA-CVA GIRR delta | GIRR delta buckets, eligible hedge offset, ineligible hedge rejection, invalid tenor cases, and deterministic replay. |
| `packages/frtb-cva/tests/test_cva_sa_cva_fixture_workflow.py` | SA-CVA fixture workflow | Expected capital, weighted-sensitivity payloads, invalid-case failures, and determinism. |
| `packages/frtb-cva/tests/test_cva_arrow_batch.py` | Arrow and batch boundary | Row/batch/handoff parity for BA-CVA and SA-CVA fixture cases. |

## Unit, Property, And Comparator Evidence

- `test_cva_ba_cva_reduced.py` includes an independent MAR50.14 oracle.
- `test_cva_ba_cva_full.py`, `test_cva_hedges.py`, and
  `test_cva_scope.py` cover hedge and method routing.
- `tests/risk_classes/` covers implemented SA-CVA GIRR, FX, CCS, RCS, equity,
  and commodity paths.
- `test_cva_properties.py` checks monotonicity and hedge-benefit properties.
- `test_cva_external_comparator.py` protects the supported slice against a
  committed comparator.
- `test_cva_unsupported_features.py` checks fail-closed unsupported runtime
  paths.

## Residual Evidence Gaps

The package has no bank-data validation, supervisory benchmark, or production
monitoring history. Those gaps are why the maturity registry remains
`partial_runtime`.
