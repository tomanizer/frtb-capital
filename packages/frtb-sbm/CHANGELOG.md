# Changelog

All notable changes to `frtb-sbm` will be documented here.

## [Unreleased]

## [0.7.5] - 2026-05-30

### Fixed

- Consolidate MAR21.6 correlation-scenario adjustment into
  `apply_correlation_scenario_definition`; `adjust_correlation_for_scenario`
  now delegates to profile-owned reference data.

## [0.7.4] - 2026-05-30

### Added

- `curvature.py` with canonical `CurvatureInput` parsing, up/down shock validation,
  worst-branch helper, and explicit fail-closed curvature capital gates (SBM-CURV-001).
- MAR21.5 `basel_mar21_curvature` citation registry entry and `curvature_citation_ids`.
- `tests/test_curvature.py` covering contract validation and capital-path rejection.

### Changed

- Expanded `CurvatureInput` with `risk_class`, `risk_factor`, and `amount_currency`.
- Curvature measure requests on BASEL_MAR21 now report curvature-specific unsupported
  errors rather than generic phase-1 capital messaging.

## [0.7.2] - 2026-05-30

### Fixed

- Remove dead `aggregate_equity_delta_intra_bucket` helper; bucket 11 uses shared
  `absolute_weight_intra` aggregation only.
- Validate sensitivities once per `calculate_sbm_capital` call; scope checks in
  `ensure_sbm_run_supported` no longer re-walk validation.
- Route phase-1 unsupported profile/path errors through `ensure_sbm_capital_paths_supported`
  with consistent capital-layer messages.
- Sort equity and commodity inter-bucket pairs with cited bucket-number guards.

### Changed

- Document risk-class-specific semantics for `qualifier` on sensitivity models.
- Remove unused audit `_normalise` helpers from runtime modules (test helpers retained).

## [0.7.1] - 2026-05-30

### Fixed

- Correct MAR21.57 Table 5 inter-bucket gamma lookup (`col - row - 1`) and trim
  sector-gamma row lengths; regenerate `csr_nonsec_delta_v1` expected capital.
- Validate CSR non-securitisation `qualifier` at the weighting boundary.
- Union MAR21.54 and MAR21.55 intra-bucket citations when index and non-index
  buckets are both present.

## [0.7.0] - 2026-05-30

### Added

- CSR non-securitisation delta cited reference data (MAR21.51-MAR21.57),
  `risk_classes/csr_nonsec.py`, and `weight_csr_nonsec_delta_sensitivities`.
- Synthetic `tests/fixtures/csr_nonsec_delta_v1/` replay bundle with negative cases.
- `tests/risk_classes/test_csr_nonsec.py` covering weights, correlations, bucket-16
  absolute aggregation, and fixture replay.

### Changed

- `calculate_sbm_capital` supports homogeneous CSR non-securitisation delta inputs.
- Profile hash and support map include CSR non-securitisation delta measure.
- Existing fixture profile hashes updated for expanded reference payload.


## [0.6.1] - 2026-05-30

### Fixed

- Apply Basel MAR21.7 portfolio-level correlation scenario selection in
  `calculate_sbm_capital` by summing risk-class scenario totals before selecting
  the maximum combined total; align per-class selected capital and buckets to
  the portfolio scenario for reconciliation.
- Propagate risk-specific intra- and inter-bucket Basel citation ids into
  aggregation audit records for GIRR delta/vega and FX delta paths.
- Use distinct scenario-selection branch ids per GIRR risk measure.

### Added

- `portfolio_scenario_totals`, `selected_portfolio_scenario`, and
  `portfolio_scenario_selection` on `SbmCapitalResult`.
- Combined GIRR delta + GIRR vega + FX delta MAR21.7 regression test.

### Changed

- Updated `REGULATORY_ASSUMPTIONS.md` to reflect supported delta/vega slices.

## [0.6.0] - 2026-05-30

### Added

- Equity and commodity delta cited reference data (MAR21.71-MAR21.85),
  `risk_classes/equity.py` and `risk_classes/commodity.py` assembly, and
  weighted-sensitivity helpers on the shared aggregation engine.
- Synthetic `tests/fixtures/equity_delta_v1/` and
  `tests/fixtures/commodity_delta_v1/` replay bundles with negative cases.
- `tests/risk_classes/test_equity.py` and `tests/risk_classes/test_commodity.py`
  covering weighting, intra/inter correlations, bucket-11 absolute aggregation,
  and fixture replay.

### Changed

- `calculate_sbm_capital` supports homogeneous equity and commodity delta inputs.
- Profile hash and support map include equity and commodity delta measures.
- Existing GIRR, FX, and fixture expected outputs updated for expanded profile hash.

### Fixed

- Equity spot/repo risk-weight lookup now compares normalised factor strings with `==`.
- Commodity delta bucket-id sorting syntax in `risk_classes/commodity.py`.

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
