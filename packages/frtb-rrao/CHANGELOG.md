# Changelog

All notable changes to `frtb-rrao` will be documented here.

## [Unreleased]

## [0.12.2a1] - 2026-06-29

### Fixed

- Wrap Arrow object conversion failures in RRAO handoff adapters and reuse the common decoder. (#405)

### Added

- Add an Arrow-backed RRAO batch path that calculates residual-risk add-ons
  without accepted-row `RraoPosition` materialization. (#300)
- Add `to_component_summary`, projecting an `RraoCapitalResult` onto the
  shared `frtb_common.ComponentCapitalSummary` consumed by suite orchestration.
  See ADR 0029 and ADR 0033. (#359)
- Enable PRA_UK_CRR RRAO profile with UK CRR Article 325u citations, reference-data maps, and rrao_pra deterministic fixtures. (#513)
- Add RRAO shared attribution projection helpers and canonical contribution bundle construction. (#616)

### Breaking Changes

- Remove ADR 0033 M2 `RRAO_HANDOFF_COLUMN_SPECS`,
  `build_rrao_batch_from_handoff`, and `to_orchestration_handoff` public aliases.
  Use `RRAO_ARROW_COLUMN_SPECS`, `build_rrao_batch_from_arrow`, and
  `to_component_summary`; the component summary adapter module is now
  `frtb_rrao.component_summary`. (#474)

### Changed

- Consolidated RRAO investment-fund validation predicates into a shared helper used
  by row and batch validation paths. (#720-investment-fund-validation)
- Vectorized the RRAO Arrow/batch decision path and expanded the target-scale benchmark to report row, column-batch, and Arrow-batch performance. (#317)
- Route RRAO mechanical batch array coercion helpers through `frtb-common`. (#391)
- Removed low-value RRAO batch array pass-through wrappers in favor of direct common helper calls. (#402)
- Extract package-private RRAO batch column coercion helpers out of `batch.py`. (#403)
- Route RRAO Arrow handoff batch reads through the shared frtb-common handoff column reader. (#406)
- Route RRAO Arrow handoff null-default restoration through the shared common reader. (#432)
- Shared RRAO validation rule predicates and messages across row and batch paths. (#543)
- Delegate RRAO batch column coercion helpers to shared batch array utilities. (#707)

### Documentation

- Moved the RRAO requirement registry into package-local docs and linked the
  module front door to the canonical package evidence. (#documentation-ownership)
- Audit and reconcile RRAO documentation with the implemented canonical-input,
  batch, Arrow handoff, allocation, traceability, and fail-closed profile
  boundaries. (#363)
- Align PRA_UK_CRR status vocabulary with IMA and document unsupported fail-closed RRAO boundaries in traceability and source manifests. (#507)
- Update RRAO regulatory sources, traceability, and suite PRA profile status for mapped UK RRAO runtime. (#513)
- Document NumPy-style docstrings (issue #650). (#650)

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
