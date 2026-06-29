# Changelog

All notable changes to `frtb-ima` will be documented here.

This package follows its own version in `packages/frtb-ima/pyproject.toml`.
Suite-level release coordination is recorded in the root `CHANGELOG.md`.

## [Unreleased]

## [0.1.1a1] - 2026-06-29

### Fixed

- Fail closed on PRA_UK_CRR IMA capital entrypoints until UK-specific source mapping and fixtures exist. (#507)
- Make `frtb_ima.regimes.UnsupportedRegulatoryFeatureError` inherit from the shared `frtb_common.UnsupportedRegulatoryFeatureError` while preserving the existing IMA import path. (#511)
- Tightened PLA regulatory audit behavior: serialise the authoritative joint zone, warn on calendar-free policy windows, validate observation-date ordering, and expose PLA/backtesting window co-alignment diagnostics. (#935)
- Harden IMA stress-period calibration auditability with regulatory horizon-floor validation, vectorized expected-shortfall window scoring, proxy-window warnings, and full/reduced risk-factor-set provenance. (#956)
- Harden ES/IMCC liquidity-horizon validation and models-based-capital audit output so non-finite scalar ES inputs, missing nesting evidence, and red-zone exception counts cannot silently produce unsupported IMA capital. (#970)

### Added

- Add an Arrow-backed IMA input-manifest handoff for tabular artifact lineage while keeping scenario cubes NumPy-native. (#274)
- Add Arrow-backed scenario metadata and RFET observation handoff batches for IMA. (#319)
- Enable partial PRA_UK_CRR IMA capital runtime with UK-cited RFET/NMRF routing and the `tests/fixtures/ima_pra` replay pack. (#512)
- Added IMA desk audit attribution projection to suite-wide CapitalContribution records. (#519)
- Add a public IMA contribution bundle helper for orchestration attribution integration. (#606)

### Breaking Changes

- Remove ADR 0033 M2 `IMA_*_HANDOFF_COLUMN_SPECS` and
  `build_*_from_handoff` public aliases. Use `IMA_*_ARROW_COLUMN_SPECS` and the
  `build_*_from_arrow` functions from `frtb_ima.arrow_batch`. (#474)

### Changed

- Route IMA Arrow handoff supported column decoding through the shared `read_arrow_columns` reader. (#406)
- Route IMA Arrow handoff null-default restoration through the shared common reader. (#432)
- Refactor row-based RFET evidence assessment into named observation-window, qualitative-control, and quantitative-filtering stages without changing the public assessment result. (#540)
- Delegate IMA Arrow date and timestamp array conversion to `frtb_common`. (#708)

### Documentation

- Document the Arrow tabular handoff boundary while keeping IMA scenario kernels NumPy-native. (#266)
- Reconcile IMA documentation with the current implementation after the suite
  documentation audit, including ES estimator status and sibling-package boundary
  language. (#361)
- Document coordinated PRA_UK_CRR source-mapping status and tie placeholder manifest entries to unsupported fail-closed capital runtime. (#507)
- Map UK CRR and PRA PS1/26 sources for PRA_UK_CRR IMA RFET/NMRF and document BASEL_EU_NMRF capital assumptions. (#512)
- Document NumPy-style docstrings for IMA contracts, adapters, and audit paths (issue #644). (#644)
- Document NumPy-style docstrings for IMA capital, PLA, and backtesting paths (issue #645). (#645)
- Document NumPy-style docstrings for IMA modellability, RFET, and liquidity paths (issue #646). (#646)

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
- Added structured RFET qualitative-criterion evidence and raw duplicate
  feed-quality counts to RFET assessment audit output.
- Added production-style `CapitalRunInputManifest` and `InputArtifactLineage`
  contracts for source-system lineage, checksums, sign conventions, counts, and
  validation status controls.
- Added a dependency-free `python -m frtb_ima.replay` CLI for replaying fixture
  audit NDJSON against the committed `capital_run_v1` input bundle.

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
- RFET scalar counting now excludes unverifiable observations, deduplicates
  source/vendor lineage, and requires a caller-supplied business calendar for
  policy-aware RFET classification.
- `CapitalRunResult`, desk audit records, and capital-run audit logs can now
  require and serialize compact input-lineage manifest summaries.

### Notes

- The package was migrated from `tomanizer/FRTB-IMA` with full git history
  preserved. No calculation logic changed during the monorepo bootstrap.
