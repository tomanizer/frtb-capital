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
bucket/category capital, reconciliation, attribution records, and audit
lineage.
The Arrow/batch API now has class-specific fast paths for non-securitisation,
securitisation non-CTP, and CTP inputs, with accepted rows kept columnar and
without row-dataclass fallback.
Known profiles are `US_NPR_2_0`, `BASEL_MAR22`, `EU_CRR3`, and
`PRA_UK_CRR`. Basel MAR22 securitisation non-CTP and CTP paths fail closed
until MAR22.34/MAR22.42 banking-book securitisation mappings are implemented.
EU CRR3 and UK PRA profiles are known identities but fail closed for all DRC
risk classes until Article 325w / PRA PS1/26 rulebook mappings are implemented.
Securitisation non-CTP and CTP sub-scope without supplied risk weights or
explicit replication evidence also fails closed.

Securitisation non-CTP and CTP risk weights can be supplied through typed
`DrcRiskWeightEvidence` records on `DrcCalculationContext`. Those records carry
position id, source profile, source table, source method, effective risk
weight, as-of date, source lineage, citation ids, and stale/validation flags.
The legacy raw float maps remain available as low-level compatibility inputs,
but typed evidence is the audit-ready production contract. Used evidence is
included in `DrcCapitalResult.risk_weight_evidence` and the deterministic input
hash.

Securitisation non-CTP fair-value cap handling is profile-controlled and only
uses typed `DrcFairValueCapEvidence` records. Missing cap evidence leaves market
value as gross default exposure and records a no-cap branch. Eligible evidence
applies the cap before maturity scaling when it is binding; ineligible evidence
records the reason without changing gross default exposure. Used cap evidence is
included in `DrcCapitalResult.fair_value_cap_evidence` and the deterministic
input hash.

`DrcCapitalResult.attribution_records` carries deterministic
`DrcCapitalContribution` records for row and batch runs. Stable non-floor
branches use `ANALYTICAL_EULER`; floors, zero HBR denominators, missing or
non-unique risk-weight lineage, and unsupported branch shapes emit
`UNSUPPORTED` or `RESIDUAL` records that reconcile to total DRC without changing
the capital number. Baseline-vs-candidate impact analysis remains a separate
future artifact.

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
- [ADR 0036: DRC securitisation and CTP risk-weight evidence contract](../../decisions/0036-drc-securitisation-risk-weight-evidence.md)
- [ADR 0030: DRC securitisation fair-value cap evidence](../../decisions/0030-drc-securitisation-fair-value-cap-evidence.md)
- [ADR 0031: DRC attribution method contract](../../decisions/0031-drc-attribution-method-contract.md)
