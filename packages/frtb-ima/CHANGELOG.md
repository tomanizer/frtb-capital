# Changelog

All notable changes to `frtb-ima` will be documented here.

This package follows its own version in `packages/frtb-ima/pyproject.toml`.
Suite-level release coordination is recorded in the root `CHANGELOG.md`.

## [Unreleased]

### Added

- Added model version, package code version, and policy hash identity fields to
  audit records, NDJSON serialisation, and Markdown audit reports.
- Added deterministic inputs hash support for audit records and validation-pack
  audit reports.
- Added `RegulatoryPolicy.cited_by` citations for numeric policy thresholds and
  parameters.
- Added explicit expected shortfall estimator selection with weighted
  interpolation as the policy default.
- Added deterministic reduced risk-factor set selection for the indirect IMCC
  reduced-set workflow.

### Documentation

- Added a determinism guarantee for the committed capital-run fixture and the
  boundaries of the current reproducibility claim.
- Replaced misleading regulatory "working assumption" language in IMA
  docstrings and traceability docs with cited threshold references for audit
  issue #4.

### Tests

- Added policy-hash and audit-identity regression coverage.
- Added capital-run fixture coverage for stable input hashing.
- Added coverage that every numeric `RegulatoryPolicy` field is either cited or
  documented as a structural modelling choice.
- Added closed-form expected shortfall tests for discrete-ceil and weighted
  interpolated estimators.
- Added reduced-set selector coverage for hand-calculated, single-factor,
  deterministic tie-break, and threshold-unmet cases.
- Added a Python-version-keyed SHA-256 determinism check for the full
  `capital_run_v1` fixture.
- Updated package documentation to reflect the migration into the
  `frtb-capital` monorepo under `packages/frtb-ima`.

### Changed

- Capped the runtime, development, and notebook dependency ranges to minor
  versions for supply-chain control.
- Removed regulatory numeric defaults from lower-level IMA calculation helpers;
  callers now pass explicit parameters or use policy-aware wrappers.
- Regenerated the `capital_run_v1` fixture using the weighted interpolated
  expected shortfall estimator.

### Notes

- The package was migrated from `tomanizer/FRTB-IMA` with full git history
  preserved. No calculation logic changed during the monorepo bootstrap.
