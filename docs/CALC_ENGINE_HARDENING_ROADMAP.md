# FRTB IMA calculation engine hardening roadmap

## Purpose

This roadmap tracks what remains after the May 2026 calculation-engine
hardening pass. The repository is now a credible deterministic prototype for
capital assembly from prepared upstream inputs, but it is still not a complete
regulatory implementation.

The strategic boundary remains unchanged:

1. `frtb_ima` validates and assembles capital from supplied risk-engine outputs.
2. Upstream systems provide market data, scenario generation, RFET evidence,
   stress-period choices, NMRF valuation artifacts, and desk governance inputs.
3. Orchestration code owns storage, object-store uploads, database writes,
   external telemetry, dashboards, and regulatory report packaging.

## Current state

The calculation layer currently provides:

- validated dataclass contracts for positions, risk factors, RFET evidence,
  scenario cubes, desk runs, and capital run results;
- scenario metadata and nested liquidity-horizon vector validation;
- scenario-cube builders for all-class and per-risk-class nested LH vectors;
- empirical 97.5 percent ES and LHA ES decomposition;
- constrained/unconstrained IMCC decomposition and reduced/full-set scaling
  helpers;
- reduced-set 60-business-day / 75 percent variation-explained diagnostic;
- RFET scalar classification plus audit-grade RFET evidence assessment;
- NMRF method evidence, direct robustness diagnostics, valuation instructions,
  upstream valuation-run specs, stress-artifact validation, Type A/B routing,
  and SES aggregation;
- PLA KS assessment over the policy window with optional date diagnostics;
- APL/HPL backtesting at 97.5 percent and 99.0 percent VaR with optional dated
  traces and official-holiday exclusions;
- desk-level models-based capital and PLA add-on helper;
- dependency-free structured JSON logging at policy-wrapper boundaries;
- `as_dict()` coverage and `DeskAuditRecord` / `CapitalRunAuditLog` NDJSON
  artifacts for post-run audit trails.

The current code is covered by `make check` and GitHub CI across Python 3.11
and 3.12.

## Design principles

### 1. Deterministic core

No LLMs, no hidden state, no stochastic behaviour inside the calculation path.

### 2. Explicit sign conventions

Every module must state whether input values are losses, profits, VaR
magnitudes, or P&L vectors.

### 3. Validated inputs

The engine should fail fast on invalid inputs:

- empty vectors,
- mismatched scenario counts,
- inconsistent scenario dates,
- missing LH10 full vectors,
- invalid confidence levels,
- invalid liquidity horizons,
- negative capital inputs where not allowed,
- malformed RFET evidence,
- missing NMRF stress artifacts for Type A/B NMRFs.

### 4. Explainable outputs

Capital results should expose decomposition for review:

- raw ES,
- liquidity-horizon adjusted ES,
- constrained and unconstrained IMCC,
- SES Type A and Type B contributions,
- multiplier inputs,
- PLA statistics,
- backtesting exception counts,
- final binding capital term,
- structured runtime events and post-run desk audit records.

### 5. Minimal dependency core

NumPy is the only runtime dependency. Do not add pandas, scipy, Polars,
Pydantic, DuckDB, Arrow, OpenTelemetry, or vendor SDKs to the calculation
package without an explicit architectural decision. If needed, those belong in
runner/orchestration packages that convert external data into the current
dataclass and NumPy contracts.

## Remaining roadmap

### 1. Regulatory mapping and source governance

Current state:

- Risk factors carry an assigned `LiquidityHorizon`.
- RFET evidence assessment captures eligible/excluded observations and a
  partial audit trail.

Remaining work:

- rules-based risk-factor to liquidity-horizon mapping tables;
- mapping evidence and override provenance;
- final NPR 2.0 interpretation once the proposal is finalized;
- fuller RFET qualitative criteria, vendor reliance, data-pooling eligibility,
  committed-quote handling, and supervisory override tracking.

### 2. Stress-period and reduced-set governance

Current state:

- IMCC reduced/full-set scaling and floor audit details exist.
- The reduced-set variation-explained diagnostic exists.
- NMRF valuation specs can carry supplied stress-period ids.

Remaining work:

- formal stress-window selection/calibration workflow;
- reduced risk-factor set selection and approval evidence;
- data-quality evidence for reduced sets beyond the coverage diagnostic;
- governance metadata for approval, versioning, and review.

### 3. NMRF valuation integration

Current state:

- The package selects methods, emits valuation instructions/specs, validates
  returned artifacts, extracts SES from loss vectors, and aggregates Type A/B
  capital.
- Direct, stepwise, full-revaluation, and max-loss generation functions remain
  explicitly unsupported in the capital package.

Remaining work:

- institutional pricing-engine integration contract;
- direct, stepwise, and full-revaluation artifact production outside
  `frtb_ima`;
- robustness tests comparing direct approximations to benchmark revaluations;
- stress scenario calibration governance and approval metadata.

### 4. PLA, backtesting, and desk eligibility lifecycle

Current state:

- Fed NPR 2.0 KS-only PLA path is implemented.
- Dual-level APL/HPL backtesting gates are implemented.
- Optional dated traces and official-holiday masks exist.

Remaining work:

- EU/PRA Spearman PLA metric and joint-zone logic;
- full business-calendar governance;
- trading-desk eligibility state machine, breach handling, loss of eligibility,
  and re-entry workflow;
- standardized/fallback inputs required for model-ineligible desks and PLA
  add-on workflows.

### 5. Capital completeness

Current state:

- Desk-level models-based capital and PLA add-on helper exist.

Remaining work:

- standardized market-risk capital;
- default risk charge;
- fallback capital for uncomputable affected positions;
- redesignation add-ons;
- legal-entity and firm-level consolidation.

### 6. Reporting, storage, and telemetry

Current state:

- Policy wrappers can emit compact structured JSON log events.
- Result objects can be serialized into desk/run audit records and NDJSON.

Remaining work:

- full audit report generation and `make audit` target;
- streaming NDJSON writer for very large multi-desk runs;
- orchestration-layer object-store/database/Splunk/OpenTelemetry sinks;
- optional Parquet/DuckDB analytics outside the calculation core;
- benchmark suite for repeated large desk runs.

## Performance baseline to add

Add a repeatable benchmark suite for:

- 10,000 scenarios x 5 liquidity horizons,
- 5 risk classes,
- 100 desks,
- repeated daily capital assembly,
- audit-record serialization for large desk batches.

The goal is not extreme speed. The goal is repeatable measurement and assurance
that scenario-level work remains NumPy-native while audit materialisation stays
explicit and outside the numeric hot path.
