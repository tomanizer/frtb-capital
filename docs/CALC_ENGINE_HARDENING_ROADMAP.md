# FRTB IMA calculation engine hardening roadmap

## Purpose

This repository should first make the calculation engine credible, deterministic, testable, performant, and professionally reviewable.

The strategic point is that a solid calculation engine makes the upstream gaps visible. Once the formulas, interfaces, test harnesses, and outputs are stable, the unresolved problems become clearly upstream:

- market data sourcing,
- risk-factor taxonomy,
- scenario generation,
- liquidity horizon mapping,
- RFET evidence,
- stress-period selection,
- reduced-set construction,
- desk governance,
- lineage and auditability.

This document therefore separates:

1. Calculation-engine hardening work that belongs in this repository now.
2. Upstream placeholder work that should be explicitly modelled as interfaces, assumptions, and future integration points.

## Target state for the calculation engine

The engine should be good enough that a reviewer can say:

> Given correctly prepared upstream inputs, the engine deterministically calculates the intended NPR 2.0-style FRTB IMA prototype outputs, with clear assumptions, validations, test coverage, and audit-friendly breakdowns.

It should not claim to be a full regulatory implementation until upstream data, governance, and supervisory interpretation are implemented.

## Design principles

### 1. Deterministic core

No LLMs, no hidden state, no stochastic behaviour inside the calculation path.

### 2. Explicit sign conventions

Every module must state whether input values are losses, profits, VaR magnitudes, or P&L vectors.

### 3. Validated inputs

The engine should fail fast on invalid inputs:

- empty vectors,
- mismatched scenario counts,
- inconsistent scenario dates,
- missing LH10 full vectors,
- invalid confidence levels,
- invalid liquidity horizons,
- negative capital inputs where not allowed,
- malformed RFET evidence.

### 4. Explainable outputs

Capital results should include enough decomposition to support review:

- raw ES,
- liquidity-horizon adjusted ES,
- constrained and unconstrained IMCC,
- SES Type A and Type B contributions,
- multiplier inputs,
- PLA statistics,
- backtesting exception counts,
- final binding term.

### 5. Minimal dependency core

The current low-dependency core is a strength. Keep NumPy as the only runtime dependency unless there is a clear reason to add more.

Use optional integrations later for DuckDB, Arrow, Polars, or pandas.

## Phase 1: calculation correctness and validation

### 1.1 Scenario vector validation

Add a module such as `scenario_validation.py` to validate nested liquidity-horizon vectors.

Required checks:

- LH10 exists.
- All vectors are non-empty.
- All supplied LH vectors have equal scenario length.
- Scenario IDs or dates are aligned where metadata is available.
- LH subsets are valid members of `LiquidityHorizon`.
- Optional monotonic inclusion metadata can prove that LH20/LH40/LH60/LH120 are true nested subsets.

### 1.2 Risk-factor to liquidity-horizon mapping

Add a rules-based mapping layer.

The current `RiskFactor` model stores a liquidity horizon, but a professional engine should show where that assignment comes from.

Recommended design:

- default regulatory mapping table,
- override table,
- mapping evidence field,
- validation that every risk factor has exactly one assigned LH,
- explicit placeholder for final NPR 2.0 interpretation.

### 1.3 Better expected shortfall options

The current ES implementation is fine for prototype use. Add optional calculation conventions:

- empirical top-tail mean,
- quantile-interpolated ES convention,
- scenario-weighted ES placeholder.

Default should remain simple and auditable.

### 1.4 Capital result decomposition

Add richer result dataclasses for:

- LHA ES component breakdown,
- constrained/unconstrained IMCC breakdown,
- SES Type A/Type B breakdown,
- final desk-level capital breakdown.

Do not only return scalar values.

## Phase 2: regulatory completeness of the calculation layer

### 2.1 IMCC stress scaling framework

Current `scale_stress_es()` is useful but isolated.

Add an IMCC component model that captures:

- current full ES,
- current reduced ES,
- stress reduced ES,
- stress scaling ratio,
- floor application,
- final scaled stress ES.

The reduced-set construction itself is upstream, but the calculator should expose the interface clearly.

### 2.2 SES method interfaces

Current SES is linear sensitivity × shock.

Keep this implementation, but add method abstractions:

- linear method,
- direct method placeholder,
- stepwise method placeholder,
- full-revaluation placeholder.

The unimplemented methods should raise `NotImplementedError` with clear messages and documentation.

### 2.3 PLA statistical completeness

Add:

- Spearman rank correlation,
- joint PLA assessment using KS and Spearman,
- rolling-window interface,
- data sufficiency checks,
- aligned HPL/RTPL date handling placeholder.

### 2.4 Backtesting completeness

Add:

- exception result with dates,
- APL/HPL separate outputs,
- multiplier derivation trace,
- rolling 250-business-day validation,
- placeholder for business calendars.

## Phase 3: professional engineering hardening

### 3.1 CI pipeline

Add GitHub Actions for:

- pytest,
- ruff,
- mypy,
- coverage.

### 3.2 Test depth

Add tests for:

- invalid inputs,
- sign convention edge cases,
- zero and negative values,
- large vectors,
- deterministic reproducibility,
- regression fixtures with known outputs,
- malformed upstream inputs.

### 3.3 Documentation maturity

Add:

- calculation methodology document,
- regulatory assumptions matrix,
- architecture diagram,
- model validation checklist,
- example desk calculation report.

### 3.4 Performance baseline

Add a simple benchmark suite.

Initial targets:

- 10,000 scenarios × 5 liquidity horizons,
- 100 desks,
- 5 risk classes,
- repeated daily capital assembly.

The first target is not extreme speed; it is repeatable measurement.

## Phase 4: upstream placeholders and integration seams

The engine should explicitly expose but not solve the upstream problems.

### 4.1 Market data interface

Placeholder:

- historical price series input,
- shock generation input,
- scenario ID/date metadata,
- data-quality flags.

### 4.2 RFET evidence interface

Placeholder:

- vendor/source evidence,
- committed quote versus transaction flag,
- observation eligibility decision,
- deduplication policy,
- audit trail.

### 4.3 Stress period governance interface

Placeholder:

- selected stress window,
- selection rationale,
- approval metadata,
- calibration version.

### 4.4 Reduced-set construction interface

Placeholder:

- selected reduced risk-factor set,
- coverage diagnostics,
- current/stress scaling evidence,
- governance approval.

### 4.5 Desk approval workflow interface

Placeholder:

- desk scope,
- modellability result,
- PLA state,
- backtesting state,
- capital fallback state.

## Recommended issue structure

The repo should use issues grouped as follows:

1. Calculation correctness
2. Regulatory method completeness
3. Validation and auditability
4. Performance
5. Documentation and professionalism
6. Upstream placeholders

## Definition of done for the hardened prototype

The prototype is ready for serious internal demonstration when:

- all public functions have clear sign conventions,
- invalid input handling is systematic,
- core formulas return decomposed result objects,
- tests cover normal, edge, and failure cases,
- CI runs automatically,
- regulatory assumptions are traceable,
- upstream gaps are visible as explicit interfaces rather than hidden assumptions,
- demo output looks like a desk-level capital report, not just printed scalars.
