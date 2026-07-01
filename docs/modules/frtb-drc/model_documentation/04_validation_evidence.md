# Validation Evidence

## Fixture Evidence

| Fixture or test | Scope | Evidence |
| --- | --- | --- |
| `packages/frtb-drc/tests/fixtures/drc_nonsec_v1/` | U.S. NPR 2.0 non-securitisation row path | Synthetic hand-checked positions, expected outputs, deterministic replay, and README case mapping. |
| `packages/frtb-drc/tests/test_drc_nonsec_v2_fixture.py` | Larger non-securitisation coverage | Replays the v2 synthetic fixture deterministically and checks expected bucket coverage. |
| `packages/frtb-drc/tests/fixtures/drc_sec_nonctp_v1/` | U.S. NPR 2.0 securitisation non-CTP | Hand-checked same-tranche, risk-weight, fair-value cap, HBR, and category evidence. |
| `packages/frtb-drc/tests/fixtures/drc_basel_sec_nonctp_v1/` | Basel MAR22 securitisation non-CTP | Hand-checked MAR22.31 bucket mapping, MAR22.34 typed risk-weight evidence, MAR22.34 fair-value cap, HBR, and category evidence. |
| `packages/frtb-drc/tests/fixtures/drc_eu_sec_nonctp_v1/` | EU CRR3 securitisation non-CTP | Article 325z/325aa typed risk-weight, fair-value cap, HBR, and category evidence. |
| `packages/frtb-drc/tests/fixtures/drc_pra_sec_nonctp_v1/` | PRA UK CRR securitisation non-CTP | Article 325z/325aa typed risk-weight, fair-value cap, HBR, and category evidence. |
| `packages/frtb-drc/tests/fixtures/drc_ctp_v1/` | U.S. NPR 2.0 CTP | Cross-tranche replication, CTP HBR, bucket recognition, and category total evidence. |
| `packages/frtb-drc/tests/fixtures/drc_basel_ctp_v1/` | Basel MAR22 CTP | Hand-checked MAR22.42 typed risk-weight evidence, cross-tranche replication, CTP HBR, bucket recognition, and category total evidence. |
| `packages/frtb-drc/tests/fixtures/drc_eu_ctp_v1/` | EU CRR3 CTP | Article 325ab-325ad typed risk-weight, decomposition, CTP HBR, bucket recognition, and category total evidence. |
| `packages/frtb-drc/tests/fixtures/drc_pra_ctp_v1/` | PRA UK CRR CTP | Article 325ab-325ad typed risk-weight, decomposition, CTP HBR, bucket recognition, and category total evidence. |
| `packages/frtb-drc/tests/fixtures/drc_eu_nonsec_v1/` | EU CRR3 non-securitisation | Article 325w/x/y LGD, maturity, bucket/risk-weight, HBR, and category evidence. |
| `packages/frtb-drc/tests/fixtures/drc_pra_nonsec_v1/` | PRA UK CRR non-securitisation | Article 325w/x/y LGD, maturity, bucket/risk-weight, HBR, and category evidence. |
| `packages/frtb-drc/tests/fixtures/handoff/` | Arrow batch boundary | Minimal class-specific handoffs round-trip through package-owned batches. |

## Unit And Reconciliation Tests

- `test_drc_gross_jtd.py`, `test_drc_maturity.py`, and `test_drc_netting.py`
  cover gross JTD, maturity scaling, and netting mechanics.
- `test_drc_capital.py` covers HBR, bucket capital, category aggregation, and
  reconciliation.
- `test_drc_securitisation.py` and `test_drc_ctp.py` cover the supported U.S.,
  Basel MAR22, EU CRR3, and PRA UK CRR securitisation non-CTP and CTP paths
  plus fail-closed evidence gaps.
- `test_drc_regimes.py` checks support-matrix agreement across U.S. NPR 2.0,
  Basel MAR22, EU CRR3, and PRA UK CRR profile/risk-class cells.
- `test_drc_arrow_batch.py` checks class-specific Arrow/handoff parity for
  non-securitisation, securitisation non-CTP, and CTP profiles.
- `test_drc_attribution.py` verifies analytical, residual, and unsupported
  attribution records reconcile to total DRC.

## Residual Validation Gaps

Validation remains synthetic. Production readiness would require bank-owned
source data controls, independent benchmarking, legal review of profile
mappings, and monitoring of live data quality.
