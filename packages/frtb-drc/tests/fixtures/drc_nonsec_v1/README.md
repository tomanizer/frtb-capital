# DRC Non-Securitisation V1 Fixture

This fixture is synthetic and uses only the supported U.S. NPR 2.0
non-securitisation path. It is designed to exercise the committed calculation
chain from canonical input through gross JTD, maturity scaling, net JTD, HBR,
bucket capital, category capital, and total DRC.

## Cases

| Position id | Case | Primary citation |
| --- | --- | --- |
| `pos-001-long-corp` | Long-only corporate senior debt. | `BASEL_MAR22_11`, `US_NPR_210_B_3_II` |
| `pos-002-short-corp` | Short-only corporate senior debt. | `BASEL_MAR22_13`, `US_NPR_210_B_3_II` |
| `pos-003-offset-long`, `pos-004-offset-short` | Eligible same-obligor, same-seniority offset. | `US_NPR_210_B_2` |
| `pos-005-ineligible-long`, `pos-006-ineligible-short` | Seniority-ineligible offset with rejected-offset audit record. | `US_NPR_210_B_2` |
| `pos-007-floor-maturity` | Maturity below three months, floored to 0.25 years. | `US_NPR_210_A_2_III` |
| `pos-008-linear-maturity` | Maturity below one year, linearly scaled. | `US_NPR_210_A_2_III` |
| `pos-009-defaulted` | Defaulted issuer in the defaulted bucket. | `US_NPR_210_B_1_IV`, `US_NPR_210_B_3_II` |
| `pos-010-covered-bond` | Covered bond LGD treatment in the PSE/GSE bucket. | `US_NPR_210_B_1_IV` |
| `pos-011-pse` | Public-sector entity LGD treatment in the PSE/GSE bucket. | `US_NPR_210_B_1_IV` |
| `pos-012-zero-lgd` | Zero-LGD not-recovery-linked exposure retained in gross/scaled audit records. | `US_NPR_210_B_1_IV` |

`expected_outputs.json` intentionally stores selected deterministic outputs
rather than a full result snapshot. It covers each capital stage while keeping
the fixture resilient to additive audit metadata.
