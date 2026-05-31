# Changelog

All notable changes to `frtb-cva` will be documented here.

## [Unreleased]

### Added

- Reduced BA-CVA (`BA_CVA_REDUCED`) and SA-CVA GIRR delta (`SA_CVA`) capital
  paths with audit hashing, reconciliation, and MAR50 citations (see
  `changelog.d/219.feature.md`).

### Fixed

- SA-CVA audit serialization now emits risk-class and bucket breakdowns; MAR50.55
  hedging-disallowance uses `R · Σ (WS^HDG)²` (see `changelog.d/220.fix.md` and
  ADR 0016).
- Vectorised SA-CVA aggregation, SA-CVA fixture pack (`sa_cva_girr_delta_v1`),
  property tests, and external-comparator tests per issue #220.
