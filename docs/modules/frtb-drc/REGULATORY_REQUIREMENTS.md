# FRTB DRC Regulatory Requirements

## Purpose

This document captures regulatory and implementation requirements for a
`frtb-drc` package that calculates the standardised approach default risk
capital requirement. It is a source map and build specification, not legal
advice and not a final regulatory capital interpretation.

## Primary Sources

| Source | Link | Use |
| --- | --- | --- |
| Basel Framework MAR20 | https://www.bis.org/basel_framework/chapter/MAR/20.htm | Standardised approach structure; SA is SBM plus DRC plus RRAO, MAR20.4. |
| Basel Framework MAR22 | https://www.bis.org/basel_framework/chapter/MAR/22.htm | Default risk capital main concepts, JTD, netting, hedge benefit ratio, non-securitisation, securitisation non-CTP, and CTP treatment, MAR22.1-MAR22.47. |
| U.S. NPR 2.0, 91 FR 14952 | https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959 | Proposed market risk framework, section V.A.9 Default Risk Capital Requirement, pages around 15067-15072. |
| CRR3 | https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng | EU comparison for alternative standardised approach default risk charge, CRR market-risk provisions including Article 325w and related articles. |
| EBA RTS on gross jump-to-default amounts | https://www.eba.europa.eu/legacy/regulation-and-policy/regulatory-activities/market-counterparty-and-cva-risk/regulatory-3 | EU technical reference for gross JTD amount methodology. |
| Local reference implementation | External `extract_cva` capital navigator, DRC component | Implementation inspiration for CRIF mappings, risk-weight tables, DRC risk-class split, and Euler/audit breakdowns; not included in this repository. |

## Regulatory Scope

DRC captures issuer default loss not captured by credit spread and equity shocks.
The Basel anchor is MAR22.1, which frames DRC as jump-to-default risk with
limited offsetting and hedging recognition. The U.S. NPR 2.0 proposal uses the
same high-level structure in section V.A.9: default risk capital applies to
non-securitisation debt or equity positions, securitisation positions non-CTP,
and correlation trading positions.

The package must calculate DRC for:

- non-securitisation debt and equity positions;
- securitisation positions that are not correlation trading positions;
- correlation trading portfolio default risk;
- defaulted and distressed positions when they are routed to DRC rather than
  the non-default risk capital requirement;
- model-eligible and model-ineligible desks through a single DRC calculation
  when required by the selected regulatory profile.

Out of scope for this package:

- market data sourcing;
- issuer reference-data mastering;
- pricing or fair-value generation;
- final regulatory submission templates;
- supervisor approval workflows;
- fallback capital for positions where DRC cannot be calculated.

## Required Data Model

The DRC package must define immutable, audit-grade inputs and outputs:

- `DrcPosition`: one exposure row with position id, desk id, legal entity,
  issuer or tranche id, risk class, bucket, seniority, credit quality,
  notional, market value or cumulative P&L component where required,
  long/short default direction, maturity, covered-bond or GSE flag, and source
  lineage.
- `GrossJtd`: position-level gross jump-to-default amount with long/short
  direction and LGD source.
- `NetJtd`: obligor or tranche net exposure after permitted offsetting.
- `BucketDrc`: bucket-level long, short, hedge benefit ratio, weighted exposure,
  capital, and floor information.
- `DrcCapitalResult`: risk-class total, bucket totals, audit records, rule
  profile, and source references.

All result dataclasses must be frozen. Inputs may accept raw strings at public
boundaries, but internal calculation objects should normalise to enums.

## Calculation Requirements

### DRC-REQ-001: Risk Classes

Implement three DRC risk classes:

- non-securitisation;
- securitisation non-CTP;
- securitisation CTP.

Basel source: MAR22.9-MAR22.47. U.S. source: NPR 2.0 section V.A.9.

### DRC-REQ-002: Gross JTD

For non-securitisation debt and equity positions, calculate gross default
exposure from notional, LGD, and the recognised P&L or market value adjustment
specified by the profile. The U.S. NPR text on page 15068 states the proposed
LGD values: 100 percent for equity, non-senior debt, and defaulted positions;
75 percent for senior debt unless a lower LGD is assigned; 50 percent for U.S.
PSEs; 25 percent for covered bonds and guaranteed GSE debt; and zero percent
for instruments whose value is not linked to issuer recovery.

Basel source: MAR22.9-MAR22.12. U.S. source: 91 FR 15067-15068, section V.A.9.a.i.

### DRC-REQ-003: Default Direction

Long and short direction must be defined by default loss or gain, not accounting
buy/sell sign. A position is long default risk when issuer default creates a
loss and short default risk when issuer default creates a gain.

Basel source: MAR22.10. U.S. source: 91 FR 15067, section V.A.9.

### DRC-REQ-004: Netting

Net long and short JTD exposures only where the applicable rule permits
offsetting:

- non-securitisation: offset gross long and gross short exposures to the same
  obligor, respecting seniority constraints and maturity scaling;
- securitisation non-CTP: offset within the same securitisation exposure set
  only where permitted;
- CTP: apply CTP-specific default risk aggregation.

Basel source: MAR22.13-MAR22.18, MAR22.27-MAR22.47. U.S. source: section V.A.9
steps two and three.

### DRC-REQ-005: Maturity Scaling

Apply the regulatory maturity scaling rules for positions with maturity below
one year where required, and preserve the unscaled and scaled JTD values in the
audit record.

Basel source: MAR22.15-MAR22.18. U.S. source: section V.A.9.a.

### DRC-REQ-006: Risk Weights

Provide regime-specific risk-weight tables:

- Basel/PRA letter-rating table including unrated and defaulted treatment;
- CRR CQS mapping table for EU comparison;
- U.S. NPR IG/SG/SSG and bucket mapping for non-U.S. sovereigns, PSE/GSE debt,
  corporates, and defaulted exposures;
- securitisation tranche risk weights by attachment/detachment or mapped
  banking-book securitisation treatment;
- CTP default risk treatment.

Basel source: MAR22.19-MAR22.26 and MAR22.32-MAR22.47. U.S. source: section
V.A.9 and proposed rule tables referenced there.

### DRC-REQ-007: Hedge Benefit Ratio and Bucket Capital

For each bucket, compute the hedge benefit ratio from aggregate net long and
net short JTD positions, apply prescribed risk weights, floor bucket capital at
zero where required, and retain the intermediate weighted-long and weighted-
short components.

Basel source: MAR22.21-MAR22.26. U.S. source: 91 FR 15067, section V.A.9 step
four.

### DRC-REQ-008: Category Aggregation

Sum bucket-level capital by DRC category. Do not recognise diversification
benefits across non-securitisation, securitisation non-CTP, and CTP categories
unless an explicit profile requires it. U.S. NPR section V.A.9 describes summing
category-level capital requirements without diversification across default risk
categories.

Basel source: MAR22.24-MAR22.47. U.S. source: 91 FR 15067, section V.A.9 step
five.

### DRC-REQ-009: Fallback and Unsupported Features

If required inputs are missing, the package must raise an explicit
`UnsupportedRegulatoryFeatureError` or `DrcInputError`; it must not silently
compute a placeholder. Fallback capital remains outside `frtb-drc`, but the
result should identify positions that must be routed to fallback.

U.S. source: section V.A.3.d fallback capital requirement and section V.A.9.

### DRC-REQ-010: Audit and Euler Decomposition

Expose bucket, issuer/tranche, seniority, risk weight, gross JTD, net JTD,
hedge benefit, capital contribution, and source row ids. Euler allocation is a
useful explain feature but must reconcile to total capital for every supported
scenario.

Reference implementation inspiration: `drc.py` defines `bucket_net_long`,
`bucket_net_short`, `rw_net_long`, `rw_net_short`, `capital_contrib`, marginal
columns, and Euler multiplier inputs.

## Reference Implementation Notes

The local extraction is useful for implementation shape but is not a regulatory
source. It suggests:

- a clean `drc_common.py` table/helper layer for buckets, credit quality,
  seniority, risk weights, and CRIF names;
- separate risk-class modules for `drc_nonsec`, `drc_sec_nctp`, and
  `drc_sec_ctp`;
- a CRIF mapping module for ISDA-style column names;
- an orchestration class that normalises input, enriches risk weights, computes
  capital, and emits intermediate/audit tables;
- output names for net long/short, risk-weighted long/short, marginal
  contribution, and Euler breakdown.

The new implementation should keep the same concepts but use dataclasses,
enums, pure functions, and NumPy-first calculations rather than pandas-centric
stateful components.
