# NPR 2.0 implementation audit

This audit records the May 2026 pass to make the Fed NPR 2.0 profile more
accurate, cleaner, and more testable. The implementation remains a prototype
using synthetic data only. It is not a production regulatory calculator.

## Design standard

The target design is:

- run-level regulatory policy selected through `CalculationContext`;
- small pure calculation functions with explicit scalar or vector inputs;
- vectorized NumPy operations for scenario and exception-count workloads;
- frozen dataclass result objects for audit decompositions;
- explicit unsupported-feature errors where the implementation is incomplete;
- documentation that separates implemented mechanics from open regulatory
  workflow requirements.

## Findings fixed in this pass

### SES aggregation

Prior behavior:

- Type A NMRF SES values were linearly summed.
- Type B NMRF SES used the 0.36 partial-correlation formula.
- Total SES was `SES_A + SES_B`.

Corrected behavior:

- Type A NMRF SES values now contribute through a zero-correlation
  root-sum-square term.
- Type B NMRF SES values still use the proposed 0.36 partial-correlation term.
- Total SES is one square root over the Type A term plus the Type B term.
- `SESAggregationResult` exposes counts, sums of squares, Type B linear sum,
  Type B correlated term, rho, and total SES.

### Backtesting

Prior behavior:

- Backtesting evaluated one VaR vector only.
- It produced Basel traffic-light zones, but not the NPR desk eligibility gate.

Corrected behavior:

- `trading_desk_backtest` evaluates both 97.5% and 99.0% VaR levels.
- APL and HPL exception counts are tested separately.
- The Fed policy applies limits of 30 exceptions at 97.5% and 12 exceptions at
  99.0%.
- Missing APL, HPL, or VaR values count as exceptions unless marked as
  official-holiday related.
- Short approved histories can use prorated thresholds through an explicit
  opt-in argument.

### PLA

Prior behavior:

- The scalar PLA function accepted any vector length.
- The policy wrapper did not enforce the 250-business-day window.

Corrected behavior:

- `pla_assessment_for_policy` requires the policy minimum history and evaluates
  the most recent policy window.
- The standalone `pla_assessment` remains a scalar/vector utility for tests and
  experiments.

### PLA add-on

Prior behavior:

- `models_based_capital` accepted a scalar `pla_addon` but no helper calculated
  the proposed add-on mechanics.

Corrected behavior:

- `pla_addon` computes the proposed add-on factor:
  `k = 0.5 * standardized_amber / standardized_green_amber`.
- The add-on applies only to positive capital benefit:
  `k * max(standardized_green_amber - ima_green_amber, 0)`.

## Remaining implementation gaps

These are not small code cleanups; they require explicit modeling choices or
new upstream data contracts:

- Stress scenario generation for each NMRF remains limited to a labelled
  synthetic sensitivity-shock helper. External direct, stepwise, and
  full-revaluation SES values can be recorded, but those methods are not
  generated inside this package.
- RFET qualitative checks are external inputs. Vendor/source lineage,
  data-pooling eligibility, third-party reliance, and new-issuance treatment are
  not implemented.
- Stress-period selection, reduced-set selection, 75-factor coverage
  governance, and supervisory approval workflows are not implemented.
- PLA and backtesting now expose optional dated diagnostics/traces, but they do
  not implement full business-calendar governance beyond an official-holiday
  mask supplied by the caller.
- Firm-level aggregation, standardized approach fallback, DRC, redesignation
  add-ons, and legal-entity consolidation are not implemented.
- The U.S. NPR 2.0 source remains a proposed rule. Final-rule changes must be
  reviewed before treating any profile as final regulatory capital.
