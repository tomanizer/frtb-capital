# FRTB SA SBM Regulatory Requirements

## Purpose

This document captures requirements for `frtb-sa-sbm`, the sensitivities-based
method component of the FRTB standardised approach. The package should calculate
delta, vega, and curvature capital for prescribed risk classes, apply bucket and
inter-bucket aggregation, support correlation scenarios, and produce
audit-grade risk-class and bucket breakdowns.

## Primary Sources

| Source | Link | Use |
| --- | --- | --- |
| Basel Framework MAR20 | https://www.bis.org/basel_framework/chapter/MAR/20.htm | Standardised approach structure and monthly calculation, MAR20.1-MAR20.4. |
| Basel Framework MAR21 | https://www.bis.org/basel_framework/chapter/MAR/21.htm | Sensitivities-based method definitions, delta/vega/curvature, risk classes, buckets, weights, and correlations, MAR21.1-MAR21.101. |
| Basel Framework MAR22 | https://www.bis.org/basel_framework/chapter/MAR/22.htm | Boundary with DRC. |
| Basel Framework MAR23 | https://www.bis.org/basel_framework/chapter/MAR/23.htm | Boundary with RRAO. |
| U.S. NPR 2.0, 91 FR 14952 | https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959 | Proposed standardized non-default capital requirement, section V.A.7.a, pages around 15037 onward. |
| CRR3 | https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng | EU alternative standardised approach, CRR market-risk Articles 325e-325az and related provisions. |
| Local reference implementation | `/Users/thomas/Documents/Projects/extract_cva/risk/gra/mrcm/frtb/capital_navigator/sa/sbm` | Implementation inspiration for component graph, CRIF mappings, risk-class modules, correlation scenarios, and outputs. |

## Regulatory Scope

Basel MAR20.4 states that standardised approach capital is the sum of SBM, DRC,
and RRAO. This package covers only the SBM non-default component. U.S. NPR 2.0
section V.A.7.a describes a six-step process:

1. identify risk factors and allocate them to one of seven risk classes;
2. allocate risk factors to corresponding buckets;
3. calculate sensitivities and apply prescribed risk weights;
4. aggregate weighted sensitivities within buckets;
5. aggregate bucket-level risk positions for each risk class;
6. aggregate risk-class capital under each correlation scenario.

## Required Data Model

- `SbmSensitivity`: source row id, risk class, risk measure, bucket, qualifier,
  tenor, option tenor, maturity, amount, currency, CVA/hedge tag where relevant,
  and source lineage.
- `WeightedSensitivity`: sensitivity with risk weight, scaled amount, and
  regulatory bucket/correlation identifiers.
- `BucketCapital`: bucket-level `Kb`, `Sb`, curvature floor data, and weighted
  sensitivity details.
- `RiskClassCapital`: low, medium, high correlation scenario totals.
- `SbmCapitalResult`: total SBM capital, risk-class totals, scenario selected,
  audit records, and unsupported-feature flags.

## Calculation Requirements

### SBM-REQ-001: Risk Class Coverage

Support the seven Basel/U.S. SBM risk classes:

- general interest rate risk;
- credit spread risk non-securitisation;
- credit spread risk securitisation CTP;
- credit spread risk securitisation non-CTP;
- equity risk;
- commodity risk;
- foreign exchange risk.

Basel source: MAR21 risk-class sections. U.S. source: 91 FR 15037, section
V.A.7.a.

### SBM-REQ-002: Risk Measure Coverage

Support delta, vega, and curvature where required. Vega and curvature are
required for instruments with optionality or embedded prepayment option risk.

Basel source: MAR21.2-MAR21.5 and risk-class sections. U.S. source: 91 FR
15037 and footnote 328.

### SBM-REQ-003: Risk Factor and Bucket Assignment

The package must accept caller-supplied canonical risk factors and buckets. It
may provide helpers for CRIF mappings, but trade-to-risk-factor classification
remains upstream.

Basel source: MAR21.8 and risk-class bucket tables. U.S. source: section
V.A.7.a process steps one and two.

### SBM-REQ-004: Risk Weights

Provide profile-specific risk weights for delta, vega, and curvature risk
factors by risk class, bucket, and tenor. Vega risk weights must follow the
liquidity-horizon square-root scaling where prescribed.

Basel source: MAR21 risk weight tables. Reference implementation:
`sbm_common.get_vega_rw(lh)` uses `min(0.55 * sqrt(lh / 10), 1.0)`.

### SBM-REQ-005: Intra-Bucket Aggregation

For each risk class and risk measure, aggregate weighted sensitivities within
the bucket using prescribed intra-bucket correlations and floors. Preserve
`Kb`, weighted sensitivities, and pairwise-correlation evidence.

Basel source: MAR21 aggregation sections. U.S. source: section V.A.7.a steps
three and four.

### SBM-REQ-006: Inter-Bucket Aggregation

Aggregate bucket risk positions using prescribed inter-bucket correlations and
correlation scenarios. Support low, medium, and high correlation scenarios, with
the final risk-class capital selected according to the profile.

Basel source: MAR21 aggregation sections. U.S. source: section V.A.7.a step
six. Reference implementation default config uses correlation scenarios
`0.75`, `1.0`, and `1.25`.

### SBM-REQ-007: Curvature

Implement curvature as the stress loss not captured by delta, with risk-class
specific shock direction, bucket aggregation, and floors. Curvature input must
include enough data to distinguish upward and downward scenarios.

Basel source: MAR21 curvature provisions. U.S. source: section V.A.7.a and
footnote 328.

### SBM-REQ-008: CRIF Mapping

Provide a CRIF mapping layer for ISDA-style input columns. The calculation
kernel must operate on canonical dataclasses so CSV/CRIF loading remains
replaceable.

Reference implementation: `sa/sbm/crif_mapping.py`, `constants.py`, and
`sbm_id_mappers.py`.

### SBM-REQ-009: Audit, Euler, and Reporting

Expose risk class, risk measure, bucket, qualifier, weighted sensitivity,
correlation scenario, bucket capital, risk-class capital, and capital
contribution. Euler allocation must reconcile to totals for supported
components.

Reference implementation: `sbm_model.py`, `capital.py`, `post_process.py`, and
`save_results` packages show expected capital, rho/gamma, Euler, and report
surfaces.

## Reference Implementation Notes

The local extraction suggests:

- a component graph per risk class and risk measure: rho, gamma, weighted
  sensitivity, and capital;
- separate modules for GIRR, CSR non-sec, CSR securitisation CTP,
  CSR securitisation non-CTP, equity, commodity, and FX;
- default correlation scenarios `0.75`, `1.0`, and `1.25`;
- common constants for CRIF/SBM field names;
- helper functions for vega risk weights and exponential tenor correlations;
- post-processing and persistence layers that should become audit/report
  outputs in this suite rather than runtime database dependencies.

