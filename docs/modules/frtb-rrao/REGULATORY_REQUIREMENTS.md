# FRTB RRAO Regulatory Requirements

## Purpose

This document captures requirements for `frtb-rrao`, the residual risk add-on
module under the FRTB standardised approach. RRAO is intentionally simple in
formula but difficult in classification: the package must identify positions
that carry exotic or other residual risks and calculate the add-on using cited
gross effective notional risk weights.

## Primary Sources

| Source | Link | Use |
| --- | --- | --- |
| Basel Framework MAR20 | https://www.bis.org/basel_framework/chapter/MAR/20.htm | Standardised approach structure, MAR20.4. |
| Basel Framework MAR23 | https://www.bis.org/basel_framework/chapter/MAR/23.htm | Residual risk add-on scope, formula, exclusions, and back-to-back treatment, MAR23.1-MAR23.7. |
| U.S. NPR 2.0, 91 FR 14952 | https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959 | Proposed residual risk capital requirement, section V.A.7.b, pages around 15049-15050. |
| EBA RRAO RTS page | https://www.eba.europa.eu/legacy/regulation-and-policy/regulatory-activities/market-counterparty-and-cva-risk/regulatory-2?version=2021 | EU RTS scope clarification for instruments bearing residual risks. |
| Commission Delegated Regulation (EU) 2022/2328 | https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32022R2328 | Official Journal RTS on residual risk add-on. |
| Local reference implementation | `[local_projects_path]/extract_cva/risk/gra/mrcm/frtb/capital_navigator/sa/rrao` | Implementation inspiration for risk-type mapping, 1 percent and 0.1 percent weights, and Euler breakdowns. |

## Regulatory Scope

RRAO captures risks not fully reflected in SBM or DRC. Basel MAR23 and U.S. NPR
2.0 section V.A.7.b identify two key charge types:

- 1 percent of gross notional for exotic exposures;
- 0.1 percent of gross notional for other residual risks.

The U.S. NPR identifies exotic examples such as longevity, weather, and natural
disaster risks. It identifies other residual risks such as gap risk,
correlation risk, and behavioural risks such as prepayments. It also lists
examples including correlation trading positions with three or more underlying
exposures that are not hedges of correlation trading positions, non-replicable
embedded optionality, and optionality with no stated maturity, strike, barrier,
or multiple strikes/barriers.

## Required Data Model

- `RraoPosition`: position id, desk id, legal entity, risk type,
  gross effective notional, currency, source row id, eligibility/exclusion
  flags, and classification evidence.
- `RraoClassification`: exotic, other residual risk, excluded, supervisor
  required, or unsupported.
- `RraoCapitalLine`: risk type, gross notional, risk weight, weighted notional,
  and audit source.
- `RraoCapitalResult`: total, by-risk-type totals, exclusions, and
  reconciliation details.

## Calculation Requirements

### RRAO-REQ-001: Subject Position Identification

Classify positions as exotic residual risk, other residual risk, excluded, or
unsupported. Classification must be explicit and audit-visible; no default
classification may be applied silently.

Basel source: MAR23.2-MAR23.3. U.S. source: 91 FR 15049, section V.A.7.b.i.

### RRAO-REQ-002: Exotic Add-On

For positions with exotic exposures, calculate capital as 1 percent of gross
effective notional. Examples include longevity, weather, natural disaster, and
other underlyings outside SBM and DRC risk classes.

Basel source: MAR23.2. U.S. source: 91 FR 15049 and footnote 385.

### RRAO-REQ-003: Other Residual Risk Add-On

For other residual risks, calculate capital as 0.1 percent of gross effective
notional. Examples include gap, correlation, and behavioural risk positions
identified by rule profile.

Basel source: MAR23.3. U.S. source: 91 FR 15049 and footnote 386.

### RRAO-REQ-004: Exclusions

Support explicit exclusion logic for positions that meet regulatory criteria:

- listed on an exchange;
- eligible to be cleared by a CCP or QCCP;
- options with two or fewer underlyings and no path-dependent payoff;
- exact back-to-back transactions;
- profile-specific government, GSE, hedge, or fallback exclusions.

Basel source: MAR23.4-MAR23.7. U.S. source: 91 FR 15049-15050, section
V.A.7.b.ii.

### RRAO-REQ-005: Supervisor-Directed Inclusion

The policy layer must allow a supervisor-directed inclusion flag so a position
can be forced into RRAO when other capital components do not capture its
material risks.

U.S. source: 91 FR 15049, section V.A.7.b.i.

### RRAO-REQ-006: Capital Aggregation

Total RRAO equals the simple sum of weighted gross effective notionals across
subject positions. No diversification, correlation scenario, or offsetting is
recognised unless a future profile cites it explicitly.

Basel source: MAR23.2-MAR23.3. U.S. source: section V.A.7.b.

### RRAO-REQ-007: Audit and Euler Explain

Expose risk type, classification reason, gross effective notional, risk weight,
weighted notional, exclusion reason, and source row id. Euler allocation is
trivial because capital is additive, but the result should still provide line
contributions for suite-level explain.

Reference implementation inspiration: `rrao.py` uses `RRAO_1_PERCENT`,
`RRAO_01_PERCENT`, `RRAO_0_PERCENT`, `WeightedNotional`, and grouped Euler
breakdowns.

## Reference Implementation Notes

The local extraction suggests:

- a small rule table mapping risk type to risk weight;
- an input loader that maps Axiom risk classes such as `Other` and `Exotic`
  into canonical RRAO risk types;
- capital as `RW * AmountUSD`;
- bankwide and standalone breakdown outputs;
- Euler contribution columns that equal weighted notional.

The new package should implement these mechanics as pure functions with frozen
dataclasses, not as a stateful pandas component.
