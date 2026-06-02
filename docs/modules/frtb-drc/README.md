# frtb-drc

`frtb-drc` is the Standardised Approach default risk charge package.

## Package Status

- Package directory: `packages/frtb-drc`
- Import name: `frtb_drc`
- Implementation status: partial runtime; supported U.S. NPR 2.0 row/batch paths and Basel MAR22 non-securitisation row/batch paths
- Validation status: pending

The package is importable and exposes `calculate_drc_capital` for supported
U.S. NPR 2.0 non-securitisation, securitisation non-CTP, and CTP canonical
inputs, plus Basel MAR22 non-securitisation canonical inputs. The current
runtime covers gross JTD, maturity scaling,
seniority-aware non-securitisation netting, securitisation same-tranche and
replication-group netting, CTP replication-group netting, hedge benefit ratio,
bucket/category capital, reconciliation, and attribution-ready audit lineage.
The Arrow/batch API now has class-specific fast paths for non-securitisation,
securitisation non-CTP, and CTP inputs, with accepted rows kept columnar and
without row-dataclass fallback.
Known profiles are `US_NPR_2_0`, `BASEL_MAR22`, `EU_CRR3`, and
`PRA_UK_CRR`. Basel MAR22 securitisation non-CTP and CTP paths fail closed
until MAR22.34/MAR22.42 banking-book securitisation risk-weight lineage and
fair-value-cap/decomposition contracts are implemented. EU CRR3 and UK PRA
profiles are known identities but fail closed for all DRC risk classes until
Article 325w / PRA PS1/26 rulebook mappings are implemented. Securitisation
non-CTP and CTP sub-scope without supplied risk weights or explicit
replication evidence also fails closed.

## Planning Documents

- [Product requirements](PRD.md)
- [Regulatory requirements](REGULATORY_REQUIREMENTS.md)
- [Detailed implementation requirements](DETAILED_REQUIREMENTS.md)
- [Architecture and data design](ARCHITECTURE_AND_DATA_DESIGN.md)
- [Decisions and implementation plan](DECISIONS_AND_PLAN.md)
- [Workable issue breakdown](ISSUE_BREAKDOWN.md)
- [Workable requirements](requirements/BASEL_FRTB_DRC.yml)
- [Model documentation — intended use](model_documentation/00_intended_use.md)
- [Model documentation promotion plan](../MODEL_DOCUMENTATION_PROMOTION_PLAN.md)

## Related ADRs

- [ADR 0012: Capital impact and attribution readiness](../../decisions/0012-capital-impact-attribution.md)
- [ADR 0027: DRC CTP row path](../../decisions/0027-drc-ctp-row-path.md)
- [ADR 0028: DRC securitisation non-CTP row path](../../decisions/0028-drc-securitisation-non-ctp-row-path.md)
