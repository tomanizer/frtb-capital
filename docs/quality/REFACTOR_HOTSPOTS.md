# Calculation refactor hotspots

Parent tracker: [#224](https://github.com/tomanizer/frtb-capital/issues/224) / [#234](https://github.com/tomanizer/frtb-capital/issues/234).

Long regulatory functions are acceptable when they preserve explicit audit flow.
Refactors should extract **named audit stages** with focused invariant tests rather
than generic abstractions.

## Priority order

| Priority | Location | Lines (approx.) | Rationale |
| --- | --- | ---: | --- |
| 1 | `frtb_cva.audit.validate_cva_result_reconciliation` | 110 | High reconciliation complexity; **refactored** into hash, BA-CVA, and SA-CVA stages |
| 2 | `frtb_ima.rfet_evidence.assess_rfet_evidence` | 194 | Frequent validation touchpoint; split qualitative vs quantitative gates next |
| 3 | `frtb_ima.backtesting.trading_desk_backtest_trace` | 167 | PLA/backtesting audit hotspot |
| 4 | `frtb_sbm.capital.calculate_sbm_capital` | 140 | Expanding risk-class surface |
| 5 | `frtb_sbm.aggregation.aggregate_risk_class_with_scenarios` | 121 | Scenario selection branches |
| 6 | `frtb_rrao.validation._validate_investment_fund_fields` | 121 | Classification edge cases |

## Refactor rules

- Preserve public APIs, deterministic hashes, and branch metadata unless an ADR
  documents intentional change.
- Add stage-level tests for invariants and invalid inputs.
- Keep regulatory formulae visible in package-local modules.

## Completed in audit follow-up

- CVA reconciliation split into `_validate_cva_result_hashes`,
  `_validate_ba_cva_reduced_reconciliation`, and `_validate_sa_cva_reconciliation`
  (`packages/frtb-cva/src/frtb_cva/audit.py`).
