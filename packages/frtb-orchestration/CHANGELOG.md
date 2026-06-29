# Changelog

All notable changes to `frtb-orchestration` will be documented here.

## [Unreleased]

## [0.2.1a1] - 2026-06-29

### Fixed

- Add jurisdiction-family consistency guard to `compose_standardised_approach_capital`.
  Mixed-jurisdiction SA compositions (e.g. Basel SBM + US-NPR DRC) now raise
  `OrchestrationInputError` immediately, before the missing-component or
  not-yet-implemented checks. Unrecognised profile IDs also fail closed. See ADR
  0022 and issue #241. (#241)
- Implemented Standardised Approach aggregation arithmetic and IMA fallback route recording in orchestration. (#408)

### Added

- `compose_standardised_approach_capital` now consumes the shared
  `frtb_common.ComponentCapitalSummary` for each component (`sbm_summary`,
  `drc_summary`, `rrao_summary`) and validates the component slot before the
  jurisdiction-family guard. Deprecated `*_handoff` keyword aliases remain
  available with `DeprecationWarning` during the ADR 0033 compatibility window.
  `ComponentCapitalSummary` and `StandardisedComponent` now come from
  `frtb_common`. See ADR 0029 and ADR 0033. (#359)
- Add `CapitalRunManifest` validation and Standardised Approach ingress routing
  with explicit logical handoff keys, source and handoff hashes, profile-family
  checks, and fail-closed orchestration status. (#429)
- Implement `calculate_suite_capital`: aggregate IMA, Standardised Approach
  (SBM + DRC + RRAO), and CVA capital into a deterministic top-of-house
  `SuiteCapitalResult`. Add `ImaCapitalSummary` and `recognise_ima_summary`
  for IMA audit log shapes. Fail closed on mixed calculation dates, base
  currencies, or jurisdiction families. End-to-end Basel-family synthetic
  fixture covers IMA-eligible and SA-fallback desk paths, SBM + DRC + RRAO
  subtotals, and CVA component with deterministic total reconciliation.
  Update `PACKAGE_METADATA` to `ImplementationStatus.IMPLEMENTED`. (#502)
- Add suite-level attribution aggregation for `ComponentContributionBundle` inputs, preserving incoming `CapitalContribution` records, validating bundle totals against component capital, and emitting an explicit suite residual record. (#518)
- Add a suite attribution report builder that turns component contribution bundles into a deterministic JSON-serialisable top-of-house explain payload with canonical component sections, reconciliation status, and suite residual reason. (#601)
- Add suite attribution summary projections for top contributors, residual rows, and unsupported attribution branches. (#602)

### Breaking Changes

- Remove ADR 0033 M2 handoff compatibility names from orchestration. Manifest
  constants, route classes, validation fields, and required-key arguments now use
  `INPUT_TABLE` / `input_tables`; SA composition accepts only
  `*_summary` component arguments. (#474)

### Changed

- Extract shared orchestration validation, suite jurisdiction, and suite attribution helpers without changing public composition APIs. (#541)

### Documentation

- Document the suite Arrow boundary and test that orchestration avoids private package batch internals. (#274)
- Reconciled orchestration documentation with the current fail-closed suite
  aggregation state, shared SA handoff contract, CVA result handoff, and runtime
  import boundary. (#366)
- Document NumPy-style docstrings (issue #647). (#647)

### Added

- Added initial importable scaffold with explicit unimplemented aggregation
  behavior.
- Added explicit Standardised Approach handoff validation and aggregation guards
  while aggregation arithmetic remains unavailable.
- Added CVA result handoff recognition for future top-of-house aggregation.
- Added `calculate_suite_capital` for additive `IMA + SA + CVA` aggregation from
  component summaries with jurisdiction-family, date, and currency guards (ADR
  0039).
