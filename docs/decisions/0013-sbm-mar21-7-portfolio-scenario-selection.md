# 13. SBM MAR21.7 portfolio-level correlation scenario selection

Date: 2026-05-30

## Status

Accepted

## Context

Basel MAR21.7 requires banks to compute low, medium, and high correlation
scenarios for delta, vega, and curvature capital, sum those risk-measure totals
across risk classes for each scenario, and select the largest portfolio total.
The initial `frtb-sbm` public API summed each risk-class result after that
result had already selected its own maximum scenario. That overstated combined
capital for synthetic portfolios where different risk classes peak under
different scenarios.

## Decision

`calculate_sbm_capital` applies portfolio-level MAR21.7 scenario selection when
more than one supported risk-class result is present:

1. Sum each risk class's scenario totals across present delta/vega slices.
2. Select the maximum portfolio scenario total.
3. Align each returned `RiskClassCapital` to the portfolio-selected scenario so
   `total_capital`, per-class `selected_capital`, and audit replay remain
   reconcilable.

Public results expose `portfolio_scenario_totals`,
`selected_portfolio_scenario`, and `portfolio_scenario_selection` branch
metadata. Isolated single risk-class runs preserve prior per-class semantics
while still populating portfolio fields for a consistent audit shape.

## Consequences

- Combined SBM totals decrease when risk classes previously peaked on
  different scenarios; isolated GIRR delta, GIRR vega, and FX delta fixture
  replay totals are unchanged.
- Reconciliation checks require risk-class selected scenarios to match the
  portfolio-selected scenario.
- Risk-class scenario branch ids include the risk measure
  (`girr_delta_scenario_selection`, `girr_vega_scenario_selection`).
- Intra- and inter-bucket audit records carry risk-specific Basel citation ids
  in addition to generic MAR21.4 aggregation citations.

## References

- Basel Framework MAR21.7 — correlation scenario selection.
- `packages/frtb-sbm/tests/test_sbm_public_api.py` combined fixture regression.
