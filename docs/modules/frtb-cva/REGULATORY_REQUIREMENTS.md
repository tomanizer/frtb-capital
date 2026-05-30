# FRTB CVA Regulatory Requirements

## Purpose

This document captures high-level regulatory requirements for `frtb-cva`. Issue-ready
detail, module layout, and implementation decisions live in:

- [DETAILED_REQUIREMENTS.md](DETAILED_REQUIREMENTS.md)
- [ARCHITECTURE_AND_DATA_DESIGN.md](ARCHITECTURE_AND_DATA_DESIGN.md)
- [DECISIONS_AND_PLAN.md](DECISIONS_AND_PLAN.md)
- [ISSUE_BREAKDOWN.md](ISSUE_BREAKDOWN.md)

The package should support the Basel CVA framework with profile hooks for U.S.
NPR 2.0, CRR3, and PRA comparison. CVA is distinct from market-risk SA SBM even
when SA-CVA reuses SBM-style delta and vega aggregation mechanics.

## Primary Sources

| Source | Link | Use |
| --- | --- | --- |
| Basel Framework MAR50 | https://www.bis.org/basel_framework/chapter/MAR/50.htm | CVA definitions, scope, BA-CVA, SA-CVA, eligible hedges, aggregation, and multiplier. |
| U.S. NPR 2.0, 91 FR 14952 | https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959 | Proposed CVA risk scope, CVA hedges, internal CVA risk transfers, and measure for CVA risk, section V.B. |
| CRR3 | https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng | EU CVA framework amendments, CRR Articles 382-386 and related CVA provisions. |
| EBA RTS on CVA risk of SFTs | https://www.eba.europa.eu/activities/single-rulebook/regulatory-activities/market-counterparty-and-cva-risk/regulatory-technical-standards-cva-risk-securities-financing-transactions | EU technical context for SFT CVA scope. |
| Local reference implementation | External `extract_cva` capital navigator, CVA component | Implementation inspiration for BA-CVA, SA-CVA risk-class modules, hedge/CVA netting, and capital reports; not included in this repository. |

## Regulatory Scope

Basel MAR50.1 states that CVA RWA equals CVA capital requirements multiplied by
12.5. MAR50.2-MAR50.4 define regulatory CVA and distinguish it from accounting
CVA. U.S. NPR 2.0 section V.B covers CVA risk application, covered positions,
CVA hedges, risk management requirements, and CVA measures.

The package must support:

- BA-CVA for counterparties and netting sets where the basic approach is
  selected or required;
- SA-CVA for banks approved or configured to use sensitivity-based CVA;
- eligible CVA hedge recognition;
- internal CVA risk transfer treatment where profile requirements are met;
- counterparty-level and portfolio-level aggregation;
- reporting of CVA capital, hedge effects, and source lineage.

Out of scope:

- counterparty credit exposure simulation;
- accounting CVA production;
- live hedge execution or desk governance;
- regulatory approval workflow for SA-CVA use;
- final disclosure templates.

## Required Data Model

- `CvaCounterparty`: counterparty id, legal entity, sector, rating or credit
  quality, exposure profile references, and eligibility flags.
- `CvaNettingSet`: netting set id, counterparty id, effective maturity, EAD or
  exposure-at-default input, collateral attributes where required, and source
  row id.
- `CvaHedge`: hedge id, hedge type, counterparty or index reference, risk
  factor mapping, notional, maturity, eligibility, and internal/external flag.
- `SaCvaSensitivity`: risk class, risk factor, bucket, tenor, sensitivity type,
  CVA/hedge tag, amount, and source lineage.
- `BaCvaCapitalLine`: counterparty/netting-set basic approach contribution.
- `SaCvaRiskClassCapital`: risk-class delta/vega capital details.
- `CvaCapitalResult`: total CVA capital, BA/SA method, hedge recognition,
  multiplier, audit records, and unsupported-feature flags.

## Calculation Requirements

### CVA-REQ-001: Scope and Eligibility

Classify covered transactions, excluded transactions, counterparties below
threshold treatment, and selected method. Regulatory CVA excludes own default
effect and may differ from accounting CVA.

Basel source: MAR50.1-MAR50.9. U.S. source: section V.B.2 and V.B.3.

### CVA-REQ-002: Eligible CVA Hedges

Recognise only eligible CVA hedges for the selected method. Internal CVA risk
transfers require a CVA desk or functional equivalent, written records, and
eligible hedge treatment. Ineligible internal transfers must be disregarded for
market-risk and CVA hedge benefit.

Basel source: MAR50 hedge provisions. U.S. source: 91 FR section V.A.6.c and
V.B.3; the NPR text describes CVA segment and trading desk segment treatment.

### CVA-REQ-003: BA-CVA

Implement the basic approach for CVA at counterparty/netting-set level, with
exposure, maturity, supervisory discounting, hedge recognition, and portfolio
aggregation according to the selected profile.

Basel source: MAR50 BA-CVA provisions, including MAR50.14 and following
stand-alone CVA capital treatment.

### CVA-REQ-004: SA-CVA Sensitivities

Implement SA-CVA delta and vega capital using CVA sensitivities and eligible
hedge sensitivities for the prescribed risk classes:

- interest rate;
- foreign exchange;
- counterparty credit spread;
- reference credit spread;
- equity;
- commodity.

Basel source: MAR50 SA-CVA provisions, including risk-class capital and
aggregation sections MAR50.47-MAR50.53 and related risk-class tables.

### CVA-REQ-005: CVA/Hedge Netting

Net CVA portfolio weighted sensitivities with eligible CVA hedge sensitivities
only in permitted risk-factor and bucket combinations. Preserve gross CVA,
hedge, and net weighted sensitivity values.

Basel source: MAR50 SA-CVA aggregation provisions. Reference implementation:
`sa_cva.py` and `cva_common.py` distinguish `CVA`, `HDG`, and `NET` tags and
define CVA/hedge weighted sensitivity columns.

### CVA-REQ-006: Aggregation and Multiplier

Aggregate risk-class capital into total SA-CVA or BA-CVA capital and apply the
profile multiplier where required. Expose pre- and post-multiplier amounts.

Basel source: MAR50.1 and MAR50 aggregation provisions.

### CVA-REQ-007: Exposure-at-Default Treatment

Inputs that contribute to BA-CVA must identify EAD or the exposure measure used
by the selected profile. The package must validate that exposure values are
non-negative, traceable, and aligned to counterparty/netting-set maturity.

Review focus from workspace guidance: correct exposure-at-default treatment in
CVA.

### CVA-REQ-008: Audit and Reports

Expose counterparty, netting set, risk class, bucket, CVA/hedge tag,
sensitivity, risk weight, correlation scenario, capital contribution, and source
row id. SA-CVA and BA-CVA reports should be comparable to external calculation
outputs without requiring proprietary systems.

Reference implementation inspiration: `sa_cva/*`, `ba_cva/*`, `capital_report`,
and `benchmarking` packages.

## Reference Implementation Notes

The local extraction suggests:

- separate BA-CVA and SA-CVA packages;
- SA-CVA risk-class modules for GIRR, FX, counterparty credit spread, reference
  credit spread, equity, and commodity;
- CVA and hedge tags before netting;
- risk-class-specific common modules for risk weights and correlations;
- capital report and benchmark output packages.

Some BA-CVA files are placeholders; use them only to infer intended package
boundaries, not formulas.
