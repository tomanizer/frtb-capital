# Changelog

All notable changes to `frtb-rrao` will be documented here.

## [Unreleased]

## [0.12.1] - 2026-05-30

### Fixed

- Guard against `importlib.metadata.version` returning an empty string in `__version__`.

## [0.12.0] - 2026-05-29

### Added

- Added initial importable scaffold with explicit unimplemented calculation
  behavior.
- Added package-local regulatory traceability, assumptions, and source
  manifest documentation for RRAO v1 planning.
- Added frozen public RRAO data models, canonical input validation helpers, and
  source-manifest tests.
- Added cited Basel MAR23 and U.S. NPR 2.0 rule-profile reference data,
  deterministic profile hashes, and fail-closed unsupported profile handling.
- Added RRAO classification and exclusion decision helpers for supported
  Basel MAR23 and U.S. NPR 2.0 canonical inputs.
- Added additive RRAO line add-ons, excluded zero-capital lines, and
  deterministic explain subtotals.
- Added the public canonical-input RRAO calculation API, deterministic input
  and result audit serialization, profile/input hashes, and reconciliation
  checks.
- Added the synthetic RRAO v1 validation fixture pack with expected outputs,
  invalid cases, pinned hashes, and replay tests.
- Added the optional standard-library CRIF/FNet adapter with source lineage,
  mapping warnings, rejected-row audit records, and no dataframe runtime
  dependency.
- Added the U.S. NPR 2.0 investment-fund inclusion path for cited
  `__.205(e)(3)(iii)` backstop-method portions under proposed section
  `__.211(a)(3)`.
- Added the EU CRR3 Article 325u comparison profile with Delegated Regulation
  (EU) 2022/2328 Article 1, Article 2 Annex, and Article 3 mappings.
- Added deterministic RRAO replay-hash controls and a target-scale benchmark
  command for 100,000 synthetic residual-risk positions.
- Added deterministic additive RRAO allocation report helpers for line, desk,
  legal-entity, and evidence-type contribution views.
- Added exact third-party back-to-back match-group validation, including
  deterministic two-transaction evidence and zero-capital excluded lines.
- Added external comparator tests, Hypothesis property tests, mutmut quality
  evidence, shared reconciliation tolerance helpers, and a narrowed v1 public
  API contract.
- Added the IMA-style RRAO model-documentation evidence pack and refreshed
  post-v1 status language across the RRAO docs.
- Added `rrao_sample_book_v1` deterministic integration fixture (25 positions,
  7 desks, 3 legal entities, all evidence types), `examples/rrao_fixture.py`
  loader module, and four walkthrough notebooks covering classification,
  capital explain, additive allocation, and Basel MAR23 vs US NPR 2.0
  multi-profile comparison.

### Changed

- Improved target-scale RRAO performance by avoiding repeated validation and
  replacing generic audit dataclass normalization with explicit serializers.
