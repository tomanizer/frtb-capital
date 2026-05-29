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

### Added (demo data and notebooks)

- Added `demo_data.py` with 40 synthetic non-securitisation positions across
  CORPORATE, NON_US_SOVEREIGN, PSE_GSE, and DEFAULTED buckets, covering all
  LGD tiers, maturity rungs, seniority-constraint scenarios, NOT_RECOVERY_LINKED
  instruments, and P&L-adjusted gross JTD edge cases.
- Added `demo_fixture.py` with `DrcNonSecFixture` dataclass and
  `load_drc_nonsec_v2_fixture()` / `run_fixture_workflow()` helpers for use in
  notebooks and regression tests.
- Added committed fixture files at `tests/fixtures/drc_nonsec_v2/` (positions,
  expected outputs, SHA-256 manifest) for deterministic regression testing.
- Added `test_nonsec_v2_fixture.py` with four regression tests covering stage
  output matching, deterministic replay, bucket coverage, and position count.
- Added six Jupyter notebooks at `notebooks/` (00–05) walking the full DRC
  non-securitisation pipeline from regulatory framework through gross JTD,
  maturity scaling, netting, HBR/bucket capital, and category total assembly.
- Added `examples/drc_nonsec_fixture.py` shim re-exporting fixture helpers for
  notebook import convenience.
- Added `scripts/generate_fixture.py` and `scripts/generate_notebooks.py` for
  regenerating fixture files and notebooks when demo data changes.

### Fixed

- Reject positions that fall outside a scoped DRC desk or legal-entity run
  before aggregation.
- Reject uncited DRC positions under the strict citation policy before capital
  is produced.
- Bumped `frtb-drc` package metadata for the capital-producing non-securitisation
  implementation.
