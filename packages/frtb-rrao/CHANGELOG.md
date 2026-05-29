# Changelog

All notable changes to `frtb-rrao` will be documented here.

## [Unreleased]

### Added

- Added initial importable scaffold with explicit unimplemented calculation
  behavior.
- Added package-local regulatory traceability, assumptions, and source
  manifest documentation for RRAO v1 planning.
- Added frozen public RRAO data models, canonical input validation helpers, and
  source-manifest tests.
- Added cited Basel MAR23 and U.S. NPR 2.0 rule-profile reference data,
  deterministic profile hashes, and fail-closed unsupported EU/PRA profiles.
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
