# frtb-drc

`frtb-drc` is the Standardised Approach default risk charge package.

## Package Status

- Package directory: `packages/frtb-drc`
- Import name: `frtb_drc`
- Implementation status: partial runtime; supported U.S. NPR 2.0 and Basel MAR22 row/batch paths for non-securitisation, securitisation non-CTP, and CTP; supported EU CRR3 row/batch path for non-securitisation
- Validation status: pending

The package is importable and exposes `calculate_drc_capital` for supported
U.S. NPR 2.0 and Basel MAR22 non-securitisation, securitisation non-CTP, and
CTP canonical inputs. The current runtime covers gross JTD, maturity scaling,
seniority-aware non-securitisation netting, securitisation same-tranche and
replication-group netting, CTP replication-group netting, hedge benefit ratio,
bucket/category capital, reconciliation, attribution records, and audit
lineage.
The Arrow/batch API has class-specific fast paths for non-securitisation,
securitisation non-CTP, and CTP inputs (one homogeneous `risk_class` per batch).
`calculate_drc_capital` accepts mixed risk classes in one row call; batch entrypoints
fail closed when classes are mixed.
Known profiles are `US_NPR_2_0`, `BASEL_MAR22`, `EU_CRR3`, and
`PRA_UK_CRR`. Basel MAR22 securitisation non-CTP is supported through cited
MAR22.31-MAR22.35 bucket, risk-weight evidence, fair-value cap, HBR, and
category aggregation contracts. Basel MAR22 CTP is supported through cited
MAR22.36-MAR22.45 CTP contracts and typed MAR22.42 banking-book
securitisation risk-weight evidence. EU CRR3 non-securitisation is supported
through cited Article 325w gross JTD/LGD, Article 325x netting/maturity,
Article 325y bucket/risk-weight/HBR/category mechanics, and ECAI-to-CQS
mapping evidence. EU CRR3 securitisation non-CTP, EU CRR3 CTP, and all UK PRA
paths fail closed until their profile-specific mappings are implemented.
Securitisation non-CTP and CTP sub-scope without supplied risk weights or
explicit replication evidence also fails closed.

Securitisation non-CTP and CTP risk weights can be supplied through typed
`DrcRiskWeightEvidence` records on `DrcCalculationContext`. Those records carry
position id, source profile, source table, source method, effective risk
weight, as-of date, source lineage, citation ids, and stale/validation flags.
The legacy raw float maps remain available as low-level compatibility inputs
for `US_NPR_2_0`; other profiles, including `BASEL_MAR22`, require typed
evidence. Used evidence is included in `DrcCapitalResult.risk_weight_evidence`
and the deterministic input hash.

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
the capital number. `calculate_drc_impact` provides separate
baseline-vs-candidate change-control analysis over two compatible
`DrcCapitalResult` objects; it labels stable branch deltas, unsupported branch
changes, and residual impact without treating impact records as regulatory
capital calculations.

## Boundary Flow

```mermaid
flowchart LR
  input["DRC positions<br/>row book or class-specific Arrow"]
  context["DrcCalculationContext<br/>profile, FX, evidence overlays"]
  class["Risk-class route<br/>non-sec, sec non-CTP, CTP"]
  kernel["DRC kernels<br/>gross JTD, netting, HBR, buckets"]
  result["DrcCapitalResult<br/>categories + attribution records"]
  summary["to_component_summary<br/>DRC handoff"]
  orchestration["frtb-orchestration<br/>SA composition"]

  input --> class
  context --> class
  class --> kernel --> result --> summary --> orchestration
```

## Integration journey

Code-first end-to-end flow (row multi-class vs per-class batch, automatic attribution,
batch audit boundaries, SA handoff):
[`packages/frtb-drc/docs/PACKAGE_JOURNEY.md`](../../../packages/frtb-drc/docs/PACKAGE_JOURNEY.md).

## Package-Local Documentation

- [Integration journey](../../../packages/frtb-drc/docs/PACKAGE_JOURNEY.md)
- [Requirement registry](../../../packages/frtb-drc/docs/requirements/BASEL_FRTB_DRC.yml)
- [Dataset contract](../../../packages/frtb-drc/docs/DATASET_CONTRACT.md)
- [Package README](../../../packages/frtb-drc/README.md)

## Planning Documents

- [Product requirements](PRD.md)
- [Regulatory requirements](REGULATORY_REQUIREMENTS.md)
- [Detailed implementation requirements](DETAILED_REQUIREMENTS.md)
- [Architecture and data design](ARCHITECTURE_AND_DATA_DESIGN.md)
- [Decisions and implementation plan](DECISIONS_AND_PLAN.md)
- [Profile support matrix](PROFILE_SUPPORT_MATRIX.md)
- [Workable issue breakdown](ISSUE_BREAKDOWN.md)
- [Workable requirements](../../../packages/frtb-drc/docs/requirements/BASEL_FRTB_DRC.yml)
- [Model documentation — intended use](model_documentation/00_intended_use.md)
- [Model documentation promotion plan](../MODEL_DOCUMENTATION_PROMOTION_PLAN.md)

## Related ADRs

- [ADR 0012: Capital impact and attribution readiness](../../decisions/0012-capital-impact-attribution.md)
- [ADR 0027: DRC CTP row path](../../decisions/0027-drc-ctp-row-path.md)
- [ADR 0028: DRC securitisation non-CTP row path](../../decisions/0028-drc-securitisation-non-ctp-row-path.md)
- [ADR 0036: DRC securitisation and CTP risk-weight evidence contract](../../decisions/0036-drc-securitisation-risk-weight-evidence.md)
- [ADR 0030: DRC securitisation fair-value cap evidence](../../decisions/0030-drc-securitisation-fair-value-cap-evidence.md)
- [ADR 0031: DRC attribution method contract](../../decisions/0031-drc-attribution-method-contract.md)
- [ADR 0038: Suite-wide attribution and impact contract](../../decisions/0038-suite-wide-attribution-impact-contract.md)
- [ADR 0041: DRC EU CRR3 non-securitisation profile slice](../../decisions/0041-drc-eu-crr3-nonsec-profile.md)
- [ADR 0042: DRC CRIF/vendor ingress adapter boundary](../../decisions/0042-drc-crif-vendor-ingress-boundary.md)
- [ADR 0044: DRC baseline impact analysis](../../decisions/0044-drc-baseline-impact-analysis.md)
