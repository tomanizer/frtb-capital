# frtb-drc profile support matrix

This matrix describes runtime support by rule profile and DRC risk class. The
same contract is exposed programmatically through
`frtb_drc.drc_profile_support_matrix()`.

| Profile | Risk class | Status | Reason | Citation ids | Next step |
| --- | --- | --- | --- | --- | --- |
| `US_NPR_2_0` | `NON_SECURITISATION` | `SUPPORTED` | U.S. NPR 2.0 non-securitisation row and batch capital supported. | `US_NPR_210_B_1_IV`, `US_NPR_210_A_2_III`, `US_NPR_210_B_2`, `US_NPR_210_B_3_I`, `US_NPR_210_B_3_II`, `US_NPR_210_B_3_III` | Maintain fixture hashes and attribution compatibility. |
| `US_NPR_2_0` | `SECURITISATION_NON_CTP` | `SUPPORTED` | U.S. NPR 2.0 securitisation non-CTP row and batch capital supported. | `US_NPR_210_C_1`, `US_NPR_210_C_2`, `US_NPR_210_C_3_I_II`, `US_NPR_210_C_3_III`, `US_NPR_210_C_3_IV`, `BASEL_MAR22_34` | Maintain typed evidence and legacy compatibility coverage. |
| `US_NPR_2_0` | `CORRELATION_TRADING_PORTFOLIO` | `SUPPORTED` | U.S. NPR 2.0 CTP row and batch capital supported. | `US_NPR_210_D_1`, `US_NPR_210_D_2`, `US_NPR_210_D_3_I_III`, `US_NPR_210_D_3_IV`, `US_NPR_210_D_3_IV_D`, `US_NPR_210_D_3_V` | Maintain CTP decomposition evidence coverage. |
| `BASEL_MAR22` | `NON_SECURITISATION` | `SUPPORTED` | Basel MAR22 non-securitisation row and batch capital supported. | `BASEL_MAR22_11`, `BASEL_MAR22_12`, `BASEL_MAR22_15_18`, `BASEL_MAR22_19`, `BASEL_MAR22_22`, `BASEL_MAR22_23`, `BASEL_MAR22_24`, `BASEL_MAR22_25`, `BASEL_MAR22_26` | Maintain Basel non-securitisation fixture and batch coverage. |
| `BASEL_MAR22` | `SECURITISATION_NON_CTP` | `SUPPORTED` | Basel MAR22 securitisation non-CTP row and batch capital supported with typed MAR22.34 banking-book risk-weight evidence. | `BASEL_MAR22_27`, `BASEL_MAR22_28`, `BASEL_MAR22_29`, `BASEL_MAR22_30`, `BASEL_MAR22_31`, `BASEL_MAR22_32`, `BASEL_MAR22_33`, `BASEL_MAR22_34`, `BASEL_MAR22_35` | Maintain Basel-specific typed evidence fixtures. |
| `BASEL_MAR22` | `CORRELATION_TRADING_PORTFOLIO` | `SUPPORTED` | Basel MAR22 CTP row and batch capital supported with typed MAR22.42 banking-book risk-weight and decomposition evidence. | `BASEL_MAR22_36`, `BASEL_MAR22_37`, `BASEL_MAR22_39`, `BASEL_MAR22_40`, `BASEL_MAR22_41`, `BASEL_MAR22_42`, `BASEL_MAR22_44`, `BASEL_MAR22_45` | Maintain Basel-specific CTP typed evidence fixtures. |
| `EU_CRR3` | `NON_SECURITISATION` | `SUPPORTED` | EU CRR3 non-securitisation row and batch capital supported. | `EU_CRR3_ARTICLE_325W`, `EU_CRR3_ARTICLE_325X`, `EU_CRR3_ARTICLE_325Y_1_2`, `EU_CRR3_ARTICLE_325Y_3_5`, `EU_CRR3_ARTICLE_325Y_6`, `EU_CRR3_ECAI_CQS_MAPPING` | Maintain EU CRR3 non-securitisation fixture and CQS mapping evidence. |
| `EU_CRR3` | `SECURITISATION_NON_CTP` | `FAIL_CLOSED` | EU_CRR3 securitisation non-CTP DRC because Articles 325z and 325aa and related banking-book securitisation mappings have not been implemented | `EU_CRR3_ARTICLES_325AB_325AD`, `EU_CRR3_ARTICLES_325Z_325AA`, `EU_CRR3_ARTICLE_325W`, `EU_CRR3_ARTICLE_325X`, `EU_CRR3_ARTICLE_325Y_1_2`, `EU_CRR3_ARTICLE_325Y_3_5`, `EU_CRR3_ARTICLE_325Y_6`, `EU_CRR3_ECAI_CQS_MAPPING` | Add cited profile-specific mappings and deterministic fixtures. |
| `EU_CRR3` | `CORRELATION_TRADING_PORTFOLIO` | `FAIL_CLOSED` | EU_CRR3 CTP DRC because Articles 325ab to 325ad and related CTP mappings have not been implemented | `EU_CRR3_ARTICLES_325AB_325AD`, `EU_CRR3_ARTICLES_325Z_325AA`, `EU_CRR3_ARTICLE_325W`, `EU_CRR3_ARTICLE_325X`, `EU_CRR3_ARTICLE_325Y_1_2`, `EU_CRR3_ARTICLE_325Y_3_5`, `EU_CRR3_ARTICLE_325Y_6`, `EU_CRR3_ECAI_CQS_MAPPING` | Add cited profile-specific mappings and deterministic fixtures. |
| `PRA_UK_CRR` | `NON_SECURITISATION` | `FAIL_CLOSED` | PRA_UK_CRR non-securitisation DRC because PS1/26 Chapter 3 and Appendix 1 rulebook paragraph mappings have not been implemented | `PRA_PS1_26_MARKET_RISK` | Add cited profile-specific mappings and deterministic fixtures. |
| `PRA_UK_CRR` | `SECURITISATION_NON_CTP` | `FAIL_CLOSED` | PRA_UK_CRR securitisation non-CTP DRC because PS1/26 Chapter 3 and Appendix 1 securitisation mappings have not been implemented | `PRA_PS1_26_MARKET_RISK` | Add cited profile-specific mappings and deterministic fixtures. |
| `PRA_UK_CRR` | `CORRELATION_TRADING_PORTFOLIO` | `FAIL_CLOSED` | PRA_UK_CRR CTP DRC because PS1/26 Chapter 3 and Appendix 1 CTP mappings have not been implemented | `PRA_PS1_26_MARKET_RISK` | Add cited profile-specific mappings and deterministic fixtures. |

Basel MAR22 securitisation non-CTP and CTP support requires typed
`DrcRiskWeightEvidence` records for MAR22.34 or MAR22.42, respectively. EU CRR3
support is limited to non-securitisation row and batch capital; securitisation
non-CTP and CTP paths remain fail-closed. Legacy raw float risk-weight maps are
limited to `US_NPR_2_0` compatibility use.
