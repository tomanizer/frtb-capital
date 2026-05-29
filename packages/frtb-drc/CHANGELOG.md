# Changelog

All notable changes to `frtb-drc` will be documented here.

## [Unreleased]

### Added

- Added initial importable scaffold with explicit unimplemented calculation
  behavior.
- Added versioned DRC rule-profile/reference-data APIs, including profile
  hashing that incorporates citation-backed LGD, maturity, bucket, and
  risk-weight tables.
- Added cited non-securitisation gross JTD calculation APIs with fail-closed
  unsupported risk-class gates.
- Added cited maturity-scaling APIs with audit branch metadata for maturity
  floors.
- Added same-obligor non-securitisation netting with seniority-aware offset
  rejection records.
