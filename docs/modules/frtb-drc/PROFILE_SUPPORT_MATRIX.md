# frtb-drc profile support matrix

This matrix describes runtime support by rule profile and DRC risk class. The
same contract is exposed programmatically through
`frtb_drc.drc_profile_support_matrix()`.

| Profile | Risk class | Status | Citation ids | Next step |
| --- | --- | --- | --- | --- |
| `US_NPR_2_0` | `NON_SECURITISATION` | Supported | `US_NPR_210_B_1_IV`, `US_NPR_210_B_2`, `US_NPR_210_B_3_I`, `US_NPR_210_B_3_II`, `US_NPR_210_B_3_III` | Maintain deterministic row and batch fixtures. |
| `US_NPR_2_0` | `SECURITISATION_NON_CTP` | Supported | `US_NPR_210_C_1`, `US_NPR_210_C_2`, `US_NPR_210_C_3_I_II`, `US_NPR_210_C_3_III`, `US_NPR_210_C_3_IV` | Maintain typed risk-weight and fair-value cap evidence fixtures. |
| `US_NPR_2_0` | `CORRELATION_TRADING_PORTFOLIO` | Supported | `US_NPR_210_D_1`, `US_NPR_210_D_2`, `US_NPR_210_D_3_I_III`, `US_NPR_210_D_3_IV`, `US_NPR_210_D_3_IV_D`, `US_NPR_210_D_3_V` | Maintain CTP replication-group fixtures. |
| `BASEL_MAR22` | `NON_SECURITISATION` | Supported | `BASEL_MAR22_12`, `BASEL_MAR22_15_18`, `BASEL_MAR22_19`, `BASEL_MAR22_22`, `BASEL_MAR22_24` | Maintain Basel non-securitisation row and batch fixtures. |
| `BASEL_MAR22` | `SECURITISATION_NON_CTP` | Supported | `BASEL_MAR22_27`, `BASEL_MAR22_28`, `BASEL_MAR22_29`, `BASEL_MAR22_30`, `BASEL_MAR22_31`, `BASEL_MAR22_32`, `BASEL_MAR22_33`, `BASEL_MAR22_34`, `BASEL_MAR22_35` | Maintain Basel-specific typed evidence fixtures. |
| `BASEL_MAR22` | `CORRELATION_TRADING_PORTFOLIO` | Fail closed | `BASEL_MAR22_42` | Implement MAR22.42 banking-book securitisation risk-weight evidence and CTP decomposition contract. |
| `EU_CRR3` | `NON_SECURITISATION` | Fail closed | `EU_CRR3_ARTICLE_325W` | Add Article 325w profile mappings and deterministic fixtures. |
| `EU_CRR3` | `SECURITISATION_NON_CTP` | Fail closed | `EU_CRR3_ARTICLE_325W` | Add Article 325w profile mappings and deterministic fixtures. |
| `EU_CRR3` | `CORRELATION_TRADING_PORTFOLIO` | Fail closed | `EU_CRR3_ARTICLE_325W` | Add Article 325w profile mappings and deterministic fixtures. |
| `PRA_UK_CRR` | `NON_SECURITISATION` | Fail closed | `PRA_PS1_26_CH3` | Add PRA PS1/26 Chapter 3 profile mappings and deterministic fixtures. |
| `PRA_UK_CRR` | `SECURITISATION_NON_CTP` | Fail closed | `PRA_PS1_26_CH3` | Add PRA PS1/26 Chapter 3 profile mappings and deterministic fixtures. |
| `PRA_UK_CRR` | `CORRELATION_TRADING_PORTFOLIO` | Fail closed | `PRA_PS1_26_CH3` | Add PRA PS1/26 Chapter 3 profile mappings and deterministic fixtures. |

Basel MAR22 securitisation non-CTP support requires typed
`DrcRiskWeightEvidence` records. Legacy raw float risk-weight maps are limited
to `US_NPR_2_0` compatibility use.
