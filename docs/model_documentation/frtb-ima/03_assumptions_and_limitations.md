# Assumptions And Limitations

This file summarizes the assumptions that materially shape the `frtb-ima`
prototype. The detailed source of record is
[`REGULATORY_ASSUMPTIONS.md`](../../../packages/frtb-ima/docs/REGULATORY_ASSUMPTIONS.md)
and the implementation-status inventory is
[`NPR_2_0_MARKET_RISK.yml`](../../../packages/frtb-ima/docs/requirements/NPR_2_0_MARKET_RISK.yml).

## Modelling Basis

- Fed NPR 2.0 is the default policy profile and is treated as proposed-rule
  material.
- Basel MAR30-MAR33 and MAR99 provide the conceptual baseline.
- EU CRR3 Articles 325ba-325bg and 325bk, plus Delegated Regulations (EU)
  2022/2059 and 2022/2060, are comparison anchors.
- The package is an IMA desk-level component inside the monorepo, not a full
  market-risk capital suite.

## Core Assumptions

| Area | Assumption | Rationale / control |
| --- | --- | --- |
| Scenario inputs | Scenario cube, stress histories, and NMRF artifact losses use positive-loss sign convention. | Fixture manifest and data-contract validation preserve sign semantics. |
| P&L inputs | APL, HPL, and RTPL use positive-profit convention; VaR uses positive magnitude. | Backtesting exception logic is documented and tested against this convention. |
| ES estimator | Weighted interpolated ES is the policy default. | ADR 0004 records the finite-sample estimator decision. |
| Liquidity horizons | Supported horizons are 10, 20, 40, 60, and 120 business days. | Basel MAR33 and proposed section `__.215` anchors; structural policy fields are documented. |
| LHA construction | LHA ES uses nested risk-factor vectors, not scalar scaling of final ES. | Enforced by `lha_builder.py`, `scenario_validation.py`, and tests. |
| RFET | RFET classifications are available before valuation. | Keeps classification, method selection, and valuation handoff explicit. |
| NMRF valuation | Direct, stepwise, and full-revaluation artifacts are produced upstream. | The package specifies, reconciles, validates, and consumes artifacts but does not price trades. |
| Stress periods | Stress-window selection uses supplied historical loss/severity vectors. | Raw market data, pricing, and formal calibration approval remain upstream. |
| PLA / backtesting | The policy window is treated as a supplied aligned observation set. | Full business-calendar governance is outside the current package boundary. |
| Audit records | Post-run audit records, not runtime logs, are the source of record for detailed review. | `DeskAuditRecord`, `CapitalRunAuditLog`, NDJSON, and Markdown reports are deterministic artifacts. |

## Implemented Boundaries

The following are implemented for prototype mechanics:

- validated data contracts for positions, risk factors, RFET evidence, scenario
  cubes, desk runs, and capital run outputs;
- RFET scalar and evidence-assessment paths;
- expected shortfall, LHA ES, IMCC, reduced-set diagnostics, stress-period
  selection from supplied vectors, NMRF method selection, valuation-run specs,
  valuation-run reconciliation, SES aggregation, PLA, backtesting, and desk
  capital assembly;
- deterministic synthetic fixture, validation notebooks, audit report
  rendering, and coverage/reference-vector gates.

## Material Limitations

The following are not complete production workflows:

- regulatory final-rule interpretation and legal sign-off;
- trading-desk approval lifecycle, loss of eligibility, remediation, and
  re-entry;
- SBM, DRC, RRAO, CVA, SA fallback stack capital, and firm-level consolidation;
- market-data sourcing, instrument classification, trade enrichment, vendor
  data lineage, and RFET data-pooling controls;
- institutional pricing and revaluation engines for NMRF stress artifacts;
- full business-calendar governance and official market holiday calendars;
- formal stress-period approval governance and reduced-set data-quality proof;
- production telemetry, large-run storage, Parquet/DuckDB analytics, and final
  regulatory disclosure templates;
- regulator-ready model documentation formatting, sign-off workflow, and
  independent validation report.

## Validation Implications

Independent validation should treat current evidence as calculation-mechanics
evidence. Before production use, validation would need to challenge upstream
data lineage, pricing/revaluation controls, stress-period governance,
desk-eligibility workflow, parameter governance, business-calendar controls,
and legal/regulatory interpretation.
