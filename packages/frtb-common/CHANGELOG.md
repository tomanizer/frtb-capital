# Changelog

All notable changes to `frtb-common` will be documented here.

## [Unreleased]

## [0.1.2a1] - 2026-06-29

### Fixed

- Remove unreachable Arrow object-decoder `to_pylist` fallbacks after pinning supported dtype conversion behavior. (#405)

### Added

- Added the minimal Arrow-backed normalized tabular handoff contract in
  `frtb-common`, including column specs, adapter diagnostics, explicit
  null/chunk/dictionary policies, row id validation, and deterministic handoff
  hashing. (#267)
- Add shared CRIF-to-Arrow normalization helpers with column discovery, alias
  normalization, primitive coercion, package-supplied RiskType mappings,
  accepted/rejected row partitioning, diagnostics, metadata, and source hashes. (#269)
- Added a vectorized Arrow compute fast path for static CRIF RiskType mapping
  tables while retaining the callback-capable compatibility path. (#284)
- Add the shared `ComponentResultHandoff` standardised-component orchestration
  handoff contract, with `StandardisedComponent` and `ComponentHandoffError`.
  Each SA component projects its result onto this neutral, validated shape so
  orchestration never couples to component-internal result fields. See ADR 0029. (#359)
- Add package-neutral deterministic JSON hashing helpers and SHA-256 hex digest
  validation utilities for future component hash consolidation. (#378)
- Add package-neutral Arrow-to-NumPy conversion helpers for handoff adapters. (#379)
- Add package-neutral NumPy batch array coercion helpers for component handoff builders. (#391)
- Add a shared `ColumnSpec`-driven Arrow handoff reader for package edge adapters. (#406)
- Add shared handoff-schema export helpers for converting public `ColumnSpec`
  tuples to JSON Schema and Arrow schema payloads for client ETL contract tests. (#423)
- Add suite-wide attribution and impact contract (ADR 0038): `ReconciliationStatus`
  enum, four new audit fields on `CapitalContribution` (`citations`, `input_hash`,
  `profile_hash`, `reconciliation_status`), `CapitalImpact` and `ImpactMethod` in
  `frtb_common.impact`, `ComponentContributionBundle` in
  `frtb_common.contribution_bundle`, and package-neutral contract tests. (#503)
- Add the shared `STANDALONE` attribution method for additive or standalone capital explain records. (#616)

### Breaking Changes

- Removed batch array helper re-exports from top-level `frtb_common`; import
    those helpers from `frtb_common.batch_arrays` instead. (#401)
- Remove ADR 0033 M2 handoff compatibility aliases. Use `NormalizedArrowTable`,
  `NormalizedTableError`, `ComponentCapitalSummary`, `ComponentSummaryError`,
  `read_arrow_columns`, `normalized_arrow_table_hash`,
  `column_specs_to_json_schema`, and `column_specs_to_arrow_schema`. The schema
  helper module is now `frtb_common.arrow_table_schema`. (#474)

### Changed

- Extend optional float array helpers for CVA column-wrapper migration. (#707-cva)
- Add common Arrow date and timestamp array converters for handoff adapters. (#708-ima)
- Extend batch array helper customisation for RRAO column-wrapper migration. (#707-rrao)
- Add a common Arrow helper for distinct non-null text values in adapter dispatchers. (#708-sbm)
- Reduce CRIF Arrow normalization copies for chunked columns and diagnostic paths. (#315)
- Added shared per-column null-default restoration for Arrow handoff readers. (#432)
- Add package-neutral batch column helpers for optional text, enum, optional
  float, and source-column-map coercion. (#707)
- Refactored attribution-related `as_dict` implementations to use a shared
  `frtb_common.serialization.dataclass_as_dict` helper while preserving public
  JSON field names. (#714)

### Documentation

- Reconciled `frtb-common` documentation with the current shared API surface:
  Arrow handoff, CRIF normalization, component orchestration handoff,
  serialization, regulatory citation helpers, and ADR-scoped non-goals. (#365)
- Document the `stable_json_hash` migration contract and compatibility tests for package-local hash helper migrations. (#537)
- Document NumPy-style docstrings for shared Arrow, CRIF, hashing, and handoff utilities in `frtb-common` (issue #639). (#639)

### Added

- Added initial scaffold with shared status metadata and explicit
  unsupported-feature exceptions.
- Added the `py.typed` marker to publish `frtb-common` as a typed package under
  PEP 561.
