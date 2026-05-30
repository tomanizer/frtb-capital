# Changelog

All notable changes to `frtb-sbm` will be documented here.

## [Unreleased]

## [0.5.0] - 2026-05-30

### Fixed

- Recompute intra-bucket capital under MAR21.6 correlation scenarios before
  inter-bucket aggregation, correcting selected scenario capital for multi-sensitivity
  buckets.

### Added

- `IntraBucketScenarioSpec`, `RiskClassScenarioDetail`, and `SbmRunContextSummary`
  on public results; audit serialization now preserves run context, scenario
  evidence, pairwise correlations, and scenario-selection branch metadata.
- Missing Basel citation registry entries for MAR21.4(4), MAR21.4(5), MAR21.6,
  and MAR21.7(2).

### Changed

- GIRR delta/vega and FX delta capital paths pass scenario specs through shared
  aggregation rather than pre-aggregating intra-bucket capital once.
- Synthetic fixture expected outputs updated for corrected scenario capital and
  expanded citation registry profile hash.

## [0.4.0] - 2026-05-30

### Added

- FX delta cited reference data (MAR21.14, MAR21.86-MAR21.89), `risk_classes/fx.py`
  assembly, and `weight_fx_delta_sensitivities` on the shared aggregation engine.
- Synthetic `tests/fixtures/fx_delta_v1/` replay bundle and
  `tests/risk_classes/test_sbm_fx.py`.

### Changed

- `calculate_sbm_capital` supports homogeneous FX delta inputs alongside unchanged
  GIRR delta/vega behavior.
- FX vega and curvature paths remain explicitly unsupported.
- Profile hash and support map include FX delta measure.

## [0.3.0] - 2026-05-30

### Added

- GIRR vega cited risk-weight scaling (MAR21.92), intra-bucket correlation (MAR21.93),
  and full capital path for BASEL_MAR21.
- `weight_girr_vega_sensitivities`, vega reference-data helpers, and combined
  delta/vega `calculate_sbm_capital` aggregation.
- Synthetic `tests/fixtures/girr_vega_v1/` replay bundle and `test_sbm_girr_vega.py`.

### Changed

- `SBM-WS-001` weighted-sensitivity requirement is implemented for GIRR delta and vega.
- Profile hash and support map include GIRR vega measure.

## [0.2.0] - 2026-05-30

### Added

- Public `calculate_sbm_capital` entry point for the Basel MAR21 GIRR delta slice.
- `capital.py`, `audit.py`, `weighted_sensitivity.py`, and `numeric.py` for
  weighting, aggregation wiring, deterministic hashes, and reconciliation.
- Synthetic `tests/fixtures/girr_delta_v1/` replay bundle with negative cases.
- Public API, audit, replay, fixture-workflow, and weighted-sensitivity tests.

### Changed

- Package metadata moves from scaffolded to partial implementation status.

## [0.1.0] - initial scaffold

### Added

- Added initial importable scaffold with explicit unimplemented calculation
  behavior.
