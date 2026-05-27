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

### NMRF method selection and stress artifacts

Prior behavior:

- RFET classified risk factors, but there was no explicit step that told the
  valuation layer how each Type A or Type B NMRF must be stressed.
- The capital layer could consume externally supplied SES scalars, but it did
  not validate required stress artifacts or route Type A/B NMRFs end to end.

Corrected behavior:

- `nmrf_method_selection.py` runs after RFET and emits auditable valuation
  instructions for `DIRECT`, `STEPWISE`, `FULL_REVALUATION`, or explicitly
  allowed `MAX_LOSS_FALLBACK` treatment.
- Method selection can now consume auditable evidence, including a vectorized
  direct-loss robustness diagnostic against benchmark revaluation losses.
- `nmrf_stress_spec.py` converts valuation instructions into upstream
  valuation-run specifications for calibrated direct shocks, stepwise grids,
  full-revaluation market states, or max-loss candidate scenarios.
- `nmrf_valuation_run.py` reconciles returned valuation artifacts to the
  requested specs before capital use, checking method, liquidity horizon,
  stress-period, scenario-count, scenario-id, and unexpected/duplicate artifact
  mismatches. Prototype-labelled artifacts fail reconciliation unless the caller
  explicitly opts into synthetic/demo artifacts.
- `NMRFStressArtifact` records post-valuation loss vectors with method,
  liquidity horizon, stress period, source, and provenance.
- `calculate_nmrf_ses_from_revaluation` extracts SES from vectorized upstream
  loss artifacts using the policy ES confidence level and a zero floor.
- `calculate_nmrf_capital_for_policy` validates that every Type A and Type B
  NMRF has the required artifact, applies method/LH checks when supplied, keeps
  Type A factors in IMCC plus SES, and keeps Type B factors in SES only.
- Missing Type A/B artifacts fail hard; the linear sensitivity helper remains
  approximation-only and requires explicit opt-in when used as an artifact.

### Structured logging and audit records

Prior behavior:

- Runtime observability and post-run audit records were ad hoc. Several result
  objects had `as_dict()` methods, but coverage was inconsistent and there was
  no single desk-level audit artifact.

Corrected behavior:

- `logging.py` adds a dependency-free `JSONFormatter` and structured field
  helper for calculation-boundary log records.
- Policy-wrapper boundaries can emit compact `INFO` records containing
  `run_id`, `desk_id`, `regime`, and scalar result fields; core vector
  calculators remain silent.
- Missing `as_dict()` methods were added across capital, NMRF, PLA,
  backtesting, RFET evidence, scenario validation, and run-result objects.
- `audit.py` adds `DeskAuditRecord`, `CapitalRunAuditLog`, and NDJSON
  serialization helpers for orchestration-layer post-run audit artifacts.

## Remaining implementation gaps

These are not small code cleanups; they require explicit modeling choices or
new upstream data contracts:

- Institutional pricing/revaluation for direct, stepwise, and full-revaluation
  NMRF stress artifacts remains upstream. This package records method evidence,
  specifies valuation-run requirements, reconciles returned artifacts, validates
  artifacts, extracts SES, and aggregates capital, but it is not a pricing
  engine.
- RFET qualitative checks are external inputs. Vendor/source lineage,
  data-pooling eligibility, third-party reliance, and new-issuance treatment are
  not implemented.
- Formal stress-period selection/calibration, reduced risk-factor set
  selection, reduced-set data quality evidence, and supervisory approval
  workflows are not implemented. NMRF valuation specs can carry supplied stress
  period ids and market-state references; they do not approve or calibrate
  those windows.
- PLA and backtesting now expose optional dated diagnostics/traces, but they do
  not implement full business-calendar governance beyond an official-holiday
  mask supplied by the caller.
- Firm-level aggregation, standardized approach fallback, DRC, redesignation
  add-ons, and legal-entity consolidation are not implemented.
- Full regulatory report generation, external telemetry, OpenTelemetry,
  Prometheus/Datadog metrics, streaming audit writers for very large desk
  batches, and Parquet/DuckDB audit analytics remain future orchestration-layer
  integrations.
- The U.S. NPR 2.0 source remains a proposed rule. Final-rule changes must be
  reviewed before treating any profile as final regulatory capital.
