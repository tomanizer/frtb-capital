# frtb-drc

`frtb-drc` is the Standardised Approach default risk charge package.

## Package Status

- Package directory: `packages/frtb-drc`
- Import name: `frtb_drc`
- Implementation status: partial runtime; supported non-securitisation and CTP row paths
- Validation status: pending

The package is importable and exposes `calculate_drc_capital` for supported
U.S. NPR 2.0 non-securitisation and CTP canonical inputs. The current runtime
covers gross JTD, maturity scaling, seniority-aware non-securitisation netting,
CTP replication-group netting, hedge benefit ratio, bucket/category capital,
reconciliation, and attribution-ready audit lineage. Securitisation non-CTP and
CTP sub-scope without supplied risk weights or explicit replication evidence
fail closed.

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
