# Changelog

All notable changes to `frtb-ima` will be documented here.

This package follows its own version in `packages/frtb-ima/pyproject.toml`.
Suite-level release coordination is recorded in the root `CHANGELOG.md`.

## [Unreleased]

### Documentation

- Added a determinism guarantee for the committed capital-run fixture and the
  boundaries of the current reproducibility claim.
- Replaced misleading regulatory "working assumption" language in IMA
  docstrings and traceability docs with cited threshold references for audit
  issue #4.

### Tests

- Added a Python-version-keyed SHA-256 determinism check for the full
  `capital_run_v1` fixture.
- Updated package documentation to reflect the migration into the
  `frtb-capital` monorepo under `packages/frtb-ima`.

### Changed

- Capped the runtime, development, and notebook dependency ranges to minor
  versions for supply-chain control.

### Notes

- The package was migrated from `tomanizer/FRTB-IMA` with full git history
  preserved. No calculation logic changed during the monorepo bootstrap.
