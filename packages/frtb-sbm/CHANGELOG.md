# Changelog

All notable changes to `frtb-sbm` will be documented here.

## [Unreleased]

## [0.8.1a1] - 2026-06-29

### Fixed

- Export SBM attribution and impact helpers at the top-level package boundary and
  align documentation with the implemented delta/vega analytical Euler support,
  curvature unsupported-residual behavior, and finite-difference impact contract. (#sbm-attribution-api-docs)
- Net GIRR delta duplicate rows to regulatory factor keys before intra-bucket aggregation. (#263)
- Vectorize GIRR delta intra-bucket correlation matrix construction and correlation-scenario matrix adjustment while preserving scalar-reference results. (#264)
- Make intra-bucket pairwise correlation audit evidence scale-aware with AUTO, FULL, and SUMMARY materialisation modes. (#265)
- Wrap Arrow object conversion failures in SBM handoff adapters and reuse the common decoder. (#405)

### Added

- Add SBM curvature batch and Arrow handoff capital paths for supported MAR21 risk classes. (#313-curvature)
- Add portfolio-level SBM batch and Arrow handoff dispatchers for high-volume supported paths. (#314-portfolio-dispatcher)
- Implement GIRR curvature capital, CSR securitisation non-CTP/CTP delta paths, CRIF adapter, and orchestration handoff for issue #160 follow-on (#166–#169). (#218)
- Implemented the GIRR MAR21.5 curvature branch engine with CVR+/CVR- preservation, bucket-level branch selection, psi handling, squared curvature correlations, and branch audit serialization while keeping public curvature capital gates fail-closed pending full curvature coverage. (#252)
- Implemented BASEL_MAR21 row-wise curvature capital across SBM risk classes with MAR21.96-MAR21.101 citations, curvature risk-weight lookups, squared curvature correlations, public support gates, and non-GIRR synthetic coverage. (#253)
- Implemented row-wise BASEL_MAR21 non-GIRR vega capital for FX, equity,
  commodity, CSR non-securitisation, CSR securitisation CTP, and CSR
  securitisation non-CTP under MAR21.90-MAR21.95.

  Added Table 13 vega liquidity-horizon lookups, MAR21.94 non-GIRR vega
  correlations, MAR21.95 delta-gamma inter-bucket reuse, support-map updates,
  validation, audit citations, and synthetic regression tests. Equity repo vega
  continues to fail closed because it has no capital requirement under MAR21.12. (#254)
- Expand the SBM CRIF row-dict adapter to map supported non-GIRR vega and
  curvature risk types into canonical sensitivities with per-row rejected-row
  diagnostics. (#255)
- Add the first Arrow-backed GIRR delta batch path so row-wise and handoff inputs
  route through one NumPy-backed weighting and factor-grid implementation. (#268)
- Add an SBM-owned GIRR delta CRIF-to-Arrow handoff path that consumes the common
  CRIF normalizer and feeds the existing `SbmSensitivityBatch` calculation path
  without materializing accepted rows as `SbmSensitivity` dataclasses. (#269)
- Generalized the package-owned `SbmSensitivityBatch` foundation for homogeneous
  SBM risk-class/measure paths while preserving the existing GIRR delta batch and
  Arrow handoff compatibility APIs. (#285)
- Added GIRR vega package-owned batch and Arrow handoff calculation entrypoints
  that avoid accepted-row `SbmSensitivity` materialization on the high-volume
  handoff path. (#286)
- Added package-owned batch and Arrow handoff capital entrypoints for FX,
  equity, and commodity delta paths, with row compatibility APIs routed through
  the same batch compute path. (#287)
- Add Arrow-backed package batch handoffs and capital entrypoints for CSR non-sec,
  CSR securitisation non-CTP, and CSR securitisation CTP delta paths. (#288)
- Added GIRR curvature batch builders and an Arrow validation handoff that preserves separate up/down shock arrays while leaving curvature capital fail-closed. (#289)
- Add Arrow handoff, package-owned batch, and batch-capital entrypoints for supported non-GIRR vega SBM paths. (#313)
- `to_component_summary` now returns the shared
  `frtb_common.ComponentCapitalSummary` instead of the package-local
  `SbmOrchestrationHandoff`, which is removed. The adapter is now exported from
  the package's public API. See ADR 0029. (#359)
- Publish the SBM Arrow handoff surface at the package top level and document the
  client integration contract for public onboarding workflows. (#424)
- Added the U.S. NPR 2.0 GIRR delta comparison slice with profile-owned citations, fixture evidence, and row/batch/Arrow parity tests. (#504)
- Replace SBM-FUNC-022 attribution and impact placeholders with production
  implementations: `calculate_sbm_attribution` returns analytical Euler
  `CapitalContribution` records for delta and vega branches (per ADR 0037/0038),
  with explicit `UNSUPPORTED` records for curvature (CVR floor), floors, partial
  pairwise materialisation, and alternative-S_b paths.
  `calculate_sbm_capital_impact` returns a shared `CapitalImpact` record. (#515)

### Breaking Changes

- Remove ADR 0033 M2 dynamically generated `*_HANDOFF_COLUMN_SPECS`,
  `build_*_batch_from_handoff`, `calculate_sbm_capital_from_*_handoff`,
  `calculate_sbm_portfolio_capital_from_handoffs`, and
  `to_orchestration_handoff` aliases. Use the Arrow batch constants/functions and
  `to_component_summary`; SBM adapters now live in `frtb_sbm.arrow_batch` and
  `frtb_sbm.component_summary`. (#474)

### Changed

- Vectorize non-GIRR vega and curvature intra-bucket correlation matrices with NumPy masks; honor pairwise evidence mode on curvature audit paths. (#439-refactor)
- Refactored SBM validation text checks to use the package-local `require_text`
  helper without changing public validation errors. (#717-validation)
- Reduce SBM Arrow handoff batch-construction copies for numeric, chunked, and dictionary-encoded columns. (#315)
- Route SBM Arrow handoff batch builders through the shared `read_arrow_columns` reader. (#406)
- Route SBM Arrow handoff null-default restoration through the shared common reader. (#432)
- Vectorize non-GIRR vega and curvature correlation matrix construction and extend
  SBM batch/Arrow benchmarks to cover those paths. (#439)
- Delegate SBM audit and regime payload hashing to `frtb_common.stable_json_hash`
  instead of maintaining duplicate local JSON/SHA-256 helpers. (#706)
- Delegate SBM Arrow portfolio path text extraction to `frtb_common`. (#708)

### Documentation

- Moved the SBM requirement registry into package-local docs and linked the module
  front door to the canonical package evidence. (#documentation-ownership)
- Add executable SBM demonstration notebooks covering validation fixtures, vega and curvature paths, and the Arrow handoff fast path. (#sbm-notebooks)
- Document the Arrow tabular handoff boundary while keeping SBM calculation kernels NumPy-native. (#266)
- Add split-metric SBM Arrow/batch benchmark summaries and baseline-relative budget controls. (#273)
- Published the SBM batch and Arrow handoff performance report with a reusable
  benchmark harness and checked-in synthetic baseline. (#290)
- Reconcile SBM documentation after the suite documentation audit, including the
  current BASEL_MAR21 high-volume support matrix and stale first-slice planning
  language. (#362)
- Documented SBM non-Basel profile expansion design and `SBM-NBP-*` requirements for AUDIT-IMP-003 (#501). (#501)
- Document NumPy-style docstrings for SBM batch and Arrow adapters (issue #651). (#651)
- Document NumPy-style docstrings for SBM calculation and validation (issue #652). (#652)
- Document NumPy-style docstrings for SBM reference data (issue #653). (#653)

## [0.8.0] - 2026-05-30

### Added

- ADR 0017 documenting CNH/CNY GIRR and FX delta mapping under Basel MAR21.8(c),
  MAR21.14(4), MAR21.41, and MAR21.88.
- GIRR bucket `17` for offshore renminbi (`CNH`); bucket `8` now maps to onshore
  `CNY`.
- `normalise_fx_delta_currency_code` mapping FX `CNH` inputs to the `CNY` bucket.

### Changed

- BASEL_MAR21 profile hash updates for the expanded GIRR bucket registry.
- `basel_mar21_38` citation note references MAR21.41 and ADR 0017.

## [0.7.5] - 2026-05-30

### Fixed

- Consolidate MAR21.6 correlation-scenario adjustment into
  `apply_correlation_scenario_definition`; `adjust_correlation_for_scenario`
  now delegates to profile-owned reference data.

## [0.7.4] - 2026-05-30

### Fixed

- Route `CSR_NONSEC`/`DELTA` through `compute_weighted_sensitivities` dispatch.
- Treat `importlib.metadata.version` returning `None` as unknown in `__version__`.

### Changed

- Refresh `CLAUDE.md` and `AGENTS.md` to reflect current phase-1 scope and
  `ValidationStatus.PENDING`.

## [0.7.3] - 2026-05-30

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
