# Changelog

All notable changes to `frtb-drc` will be documented here.

## [Unreleased]

## [0.1.8a1] - 2026-06-29

### Fixed

- Reject `UNRATED` DRC non-securitisation credit quality at row and batch input boundaries with a cited error instead of failing later at risk-weight lookup. (#337)
- Reject non-chargeable U.S. NPR 2.0 DRC non-securitisation bucket labels such
  as U.S. sovereign, MDB, municipal, and local-government before row or columnar
  capital calculation instead of allowing them to reach strict risk-weight lookup. (#339)
- Fix the U.S. NPR 2.0 DRC non-securitisation corporate investment-grade risk weight from 2.1% to 4.1% and regenerate affected golden outputs. (#340)

### Added

- Add a DRC non-securitisation Arrow handoff and NumPy batch capital path for
  high-volume inputs without accepted-row `DrcPosition` materialization. (#299)
- Implemented the DRC securitisation non-CTP row path with cited market-value gross default exposure, same-pool/same-tranche netting, explicit replication-group evidence, securitisation bucket taxonomy, context-supplied tranche risk weights, audit records, and a hand-checked fixture. (#335)
- Added the U.S. NPR 2.0 CTP DRC row path with market-value gross default
  exposure, explicit run-scoped CTP risk weights and offset-group evidence,
  rejected-offset audit records, CTP-wide HBR, negative bucket capital, and
  category-level cross-index aggregation. (#336)
- Add explicit FX-rate translation for multi-currency non-securitisation DRC books across the row and Arrow batch APIs. (#338)
- Extend the DRC Arrow handoff and batch capital path to securitisation non-CTP
  and CTP inputs with row-path parity, fail-closed mixed-class validation, and
  zero accepted-row `DrcPosition` materialization. Keep exact-group sec/CTP
  rejected-offset audit records bounded by representative groups instead of
  pairwise long/short group products. (#351)
- Add cited Basel MAR22 non-securitisation DRC profile coverage and fail-closed EU/PRA profile identities. (#352)
- Add typed securitisation non-CTP and CTP risk-weight evidence records with lineage, citations, stale checks, result capture, and input-hash participation. (#353)
- Add profile-controlled securitisation non-CTP fair-value cap evidence handling. (#354)
- Add DRC attribution records with analytical, residual, and unsupported methods
  for row and batch capital results. (#355)
- Add `to_component_summary`, projecting a `DrcCapitalResult` onto the shared
  `frtb_common.ComponentCapitalSummary` consumed by suite orchestration. See ADR
  0029 and ADR 0033. (#359)
- Enable Basel MAR22 securitisation non-CTP row and batch DRC with typed
  MAR22.34 risk-weight evidence, profile-specific fair-value cap citations, and
  deterministic Basel fixtures. (#514)
- Migrate `DrcCapitalContribution` to the suite-wide `CapitalContribution` from
  `frtb_common.attribution` (ADR 0038). `DrcCapitalContribution` is removed from
  `data_models.py` and from the package public API; `DrcCapitalResult.attribution_records`
  now carries `tuple[CapitalContribution, ...]`. The local `AttributionMethod` StrEnum
  is also removed in favour of the shared one from `frtb_common.attribution`.
  `calculate_drc_attribution` gains `input_hash` and `profile_hash` keyword parameters
  (defaulting to `""`) and populates all four new audit fields on every emitted record:
  `citations` is taken from the source `BucketDrc.citations`; `input_hash` and
  `profile_hash` are forwarded from `DrcCapitalResult` by the `scaffold` and `batch`
  callers (both fields were already present on `DrcCapitalResult`); `reconciliation_status`
  is `RECONCILED` for `ANALYTICAL_EULER` records and `PARTIAL_RESIDUAL` for `RESIDUAL`
  and `UNSUPPORTED` records. Capital arithmetic is unchanged. (#517)
- Enable Basel MAR22 CTP row and Arrow batch DRC with typed MAR22.42 risk-weight evidence. (#582)
- Implement the EU CRR3 non-securitisation DRC row and Arrow batch vertical slice with Article 325w, Article 325x, Article 325y, and ECAI/CQS mapping citations, deterministic fixtures, and profile support-matrix coverage while keeping EU CRR3 securitisation non-CTP and CTP fail-closed. (#583)
- Add a DRC CRIF/vendor ingress adapter that maps source rows into canonical positions, class-specific Arrow handoffs, and deterministic rejected-row diagnostics. (#584)
- Add DRC baseline-vs-candidate impact analysis with branch-aware finite-difference,
  unsupported, and residual records. (#585)

### Breaking Changes

- Remove ADR 0033 M2 `*_HANDOFF_COLUMN_SPECS`, `build_*_batch_from_handoff`,
  and `to_orchestration_handoff` public aliases. Use `*_ARROW_COLUMN_SPECS`,
  `build_*_batch_from_arrow`, and `to_component_summary`; the component summary
  adapter module is now `frtb_drc.component_summary`. (#474)

### Changed

- Refactored DRC data-model `as_dict` methods to use the shared dataclass
  serializer without changing serialized field contracts. (#718-data-model-serialization)
- Reduce DRC Arrow handoff conversion overhead and vectorize non-securitisation LGD lookup. (#316)
- Route DRC mechanical batch array coercion helpers through `frtb-common`. (#391)
- Removed low-value DRC batch array pass-through wrappers in favor of direct common helper calls. (#402)
- Extract package-private DRC batch column coercion helpers out of `batch.py`. (#403)
- Route DRC Arrow handoff batch readers through the shared `frtb-common` handoff column reader. (#406)
- Route DRC audit, batch, FX, CTP, securitisation, and profile payload hashes through a package-local wrapper over `frtb_common.stable_json_hash`. (#539)
- Delegate DRC batch column optional text, enum, optional float, and source map
  coercion wrappers to `frtb_common.batch_arrays`. (#707)

### Documentation

- Moved the DRC requirement registry into package-local docs and linked the module
  front door to the canonical package evidence. (#documentation-ownership)
- Reconciled DRC package, planning, and model documentation with the implemented U.S. NPR 2.0 securitisation non-CTP, CTP, Basel MAR22 non-securitisation, batch, and attribution support matrix. (#356)
- Refresh the DRC profile support matrix with explicit per-path reasons and add row and Arrow/batch fail-closed coverage for unsupported Basel CTP, EU CRR3, and PRA UK CRR paths. (#505)
- Document NumPy-style docstrings for DRC public models, profiles, and batch helpers (issue #642). (#642)
- Document NumPy-style docstrings for DRC calculation, evidence, and adapter paths (issue #643). (#643)

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
