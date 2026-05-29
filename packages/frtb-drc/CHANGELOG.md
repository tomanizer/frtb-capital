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
- Added bucket-level and category-level non-securitisation DRC capital APIs with
  HBR and bucket-floor audit metadata.
- Added public non-securitisation DRC API results with deterministic audit and
  replay snapshots.

### Fixed

- Reject positions that fall outside a scoped DRC desk or legal-entity run
  before aggregation.
- Reject uncited DRC positions under the strict citation policy before capital
  is produced.
- Bumped `frtb-drc` package metadata for the capital-producing non-securitisation
  implementation.
