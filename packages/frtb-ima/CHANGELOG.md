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
- Added Hypothesis property tests for ES, PLA statistics, LHA ES, IMCC, SES,
  and desk-level capital assembly.
- Added mutmut configuration and baseline documentation for mutation testing on
  core calculation modules.
- Added a deterministic target-scale performance benchmark covering nested LH
  vectors, LHA ES, IMCC, SES, PLA/backtesting checks, capital assembly, and
  NDJSON audit serialisation.
- Added dependency-free business-calendar contracts for RFET, PLA/backtesting,
  and stress-period observation-window evidence.
- Added RFET evidence contracts for source/vendor/feed/venue lineage,
  data-pooling/vendor-audit evidence, timestamp normalisation,
  representativeness methodologies, and policy-governed new-issuance prorating.
- Added production-style `CapitalRunInputManifest` and `InputArtifactLineage`
  contracts for source-system lineage, checksums, sign conventions, counts, and
  validation status controls.

### Documentation

- Added a determinism guarantee for the committed capital-run fixture and the
  boundaries of the current reproducibility claim.
- Linked the validation-pack guide to the formal suite-level FRTB-IMA model
  documentation pack.
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
- Added deterministic Hypothesis `dev` and `ci` profiles, with CI running the
  thorough profile.
- Added focused expected-shortfall helper coverage for direct sorted-loss input
  validation.
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
- PLA, backtesting, RFET, and stress-period policy paths now record
  supplied-calendar source/version metadata when a business calendar is
  provided.
- RFET evidence assessments now expose immutable source/vendor, exclusion,
  bucket, and representativeness-methodology summary counts for audit output.
- `CapitalRunResult`, desk audit records, and capital-run audit logs can now
  require and serialize compact input-lineage manifest summaries.

### Notes

- The package was migrated from `tomanizer/FRTB-IMA` with full git history
  preserved. No calculation logic changed during the monorepo bootstrap.
