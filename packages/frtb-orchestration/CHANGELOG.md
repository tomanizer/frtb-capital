# Changelog

All notable changes to `frtb-orchestration` will be documented here.

## [Unreleased]

### Added

- Added initial importable scaffold with explicit unimplemented aggregation
  behavior.
- Added explicit Standardised Approach handoff validation and aggregation guards
  while aggregation arithmetic remains unavailable.
- Added CVA result handoff recognition for future top-of-house aggregation.
- Added `calculate_suite_capital` for additive `IMA + SA + CVA` aggregation from
  component summaries with jurisdiction-family, date, and currency guards (ADR
  0039).
