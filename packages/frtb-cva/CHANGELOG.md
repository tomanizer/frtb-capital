# Changelog

All notable changes to `frtb-cva` will be documented here.

## [Unreleased]

## [0.1.1a1] - 2026-06-29

### Fixed

- Expand the SA-CVA GIRR delta validation fixture to assert weighted sensitivity,
  bucket, and risk-class outputs, including ineligible hedge and missing
  risk-weight cases. (#199)
- Fix SA-CVA audit serialization, MAR50.55 hedging-disallowance formula, sign
  convention validation, SA-CVA input routing, vectorised aggregation, SA-CVA
  fixture pack, property and external-comparator tests, and documentation refresh
  per issue #220 audit findings.

  **Breaking input contract**

  - `CvaNettingSet.sign_convention` no longer accepts `positive_loss` for EAD;
    use `non_negative` (or omit for the default). Callers and fixtures that
    still pass `positive_loss` on netting sets will raise `CvaInputError`.
  - `calculate_cva_capital` with `method=SA_CVA` now raises `CvaInputError` when
    `counterparties` or `netting_sets` are supplied, instead of accepting them
    and setting `SA_CVA_IGNORES_COUNTERPARTY_NETTING_SET_INPUTS`. Orchestration
    or other callers must not pass BA-CVA portfolio inputs on the SA-CVA path.

  (#220)
- Fix reduced BA-CVA portfolio aggregation to use the MAR50.14 correlation
  weighting `sqrt((ρ·ΣSCVA)² + (1−ρ²)·ΣSCVA²)` instead of the incorrect
  `sqrt(ρ·(ΣSCVA)² + (1−ρ)·ΣSCVA²)`. With ρ=0.5 this corrects the systematic /
  idiosyncratic split from 0.50/0.50 to 0.25/0.75. Multi-counterparty reduced
  BA-CVA portfolio capital decreases (more diversification credit); single-
  counterparty results are unchanged. The reconciliation test now checks against
  an independent MAR50.14 oracle rather than re-deriving the implementation
  expression. See ADR 0020 and issue #240. (#240)
- Fix BA-CVA stand-alone SCVA to apply the MAR50.15 supervisory factor as a
  divisor (1/α = 1/1.4) instead of a multiplier. Every netting-set SCVA and the
  downstream reduced portfolio K_reduced decrease by a factor of α² = 1.96
  relative to the previous incorrect values. The existing test oracles that used
  `alpha * ...` are replaced with `... / alpha`; a new independent MAR50.15
  oracle test validates the absolute expected value. See ADR 0021 and issue #257. (#257)
- Wrap Arrow object conversion failures in CVA handoff adapters and reuse the common decoder. (#405)
- Correct SA-CVA RCS qualified-index routing and correlations so buckets 16/17 use qualified-index treatment while bucket 8 remains a single-name RCS bucket. (#700)
- Require mixed carve-out SA-CVA sensitivity scope evidence so SA-CVA runs on an
  audited non-carved slice rather than silently combining full-book sensitivities
  with BA-CVA carve-out capital. (#701)
- Correct SA-CVA RCS delta risk weights for HY/NR buckets against MAR50.68 Table 10, including bucket 8 at 2%. (#702)
- Separate SA-CVA hedge purpose and instrument metadata from BA-CVA CDS hedge
  types so exposure-component hedges no longer need a BA hedge type while BA-CVA
  full still fails closed without one. (#703)
- Fail closed U.S. NPR, EU CRR3, and UK PRA CVA comparison-profile support-matrix cells until profile-specific fixture evidence or an explicit equivalence decision exists. (#760)
- Enforce MAR50 CVA validation floors and record SA-CVA variance-floor audit metadata. (#981)

### Added

- Implement SA-CVA phase 3 remaining risk classes (FX, CCS, RCS, equity, commodity, GIRR/FX vega) per MAR50.59–MAR50.77 with cited reference tables and risk-class tests. (#216)
- Deliver frtb-cva phase 4: full BA-CVA hedge recognition, mixed-method assembly,
  qualified-index routing, CRIF adapter, orchestration CVA handoff, performance
  benchmarks, and attribution/impact helpers. (#217)
- Implement reduced BA-CVA (MAR50.14–15) and SA-CVA GIRR delta (MAR50.53–57)
  as phase 1/2 of `frtb-cva`. Public `calculate_cva_capital` supports
  `BA_CVA_REDUCED` and `SA_CVA` methods with full audit hashing, reconciliation,
  and regulatory citations. Package maturity advances from `SCAFFOLDED` to `PARTIAL`. (#219)
- Add Arrow-backed CVA counterparty, netting-set, hedge, and SA-CVA sensitivity
  batches with high-volume BA-CVA and SA-CVA batch calculation entrypoints. (#301)
- Add ADR 0033 Arrow-ingest vocabulary for CVA batch inputs, including
  `*_ARROW_COLUMN_SPECS` and `build_*_batch_from_arrow` canonical names, while
  retaining deprecated `*_HANDOFF_COLUMN_SPECS` and `build_*_batch_from_handoff`
  compatibility aliases. (#359)
- Add a runtime-readable CVA profile/method support matrix with MAR50.9 fail-closed status, CCS vega regulatory-absence status, comparison-profile fail-closed cells, traceability docs, and maturity evidence. (#506)
- Migrate `CvaCapitalImpact` to the suite-wide `frtb_common.impact.CapitalImpact` (ADR 0038): `assess_cva_capital_impact` now returns a `CapitalImpact` with `component="frtb_cva"`, `method=ImpactMethod.FINITE_DIFFERENCE`, and profile hashes populated from `CvaCapitalResult`. The package-local `CvaCapitalImpact` dataclass is removed. Add `project_cva_attribution` to `frtb_cva.attribution`, which projects a `CvaAttributionResult` to a tuple of `frtb_common.attribution.CapitalContribution` records with `input_hash`, `profile_hash`, and `reconciliation_status` populated from the accompanying `CvaCapitalResult`. (#516)
- Support U.S. NPR 2.0, EU CRR3, and UK PRA CVA comparison profiles with profile-owned citations, deterministic profile hashes, support-matrix coverage, and synthetic public API regression tests. (#568)

### Breaking Changes

- Remove ADR 0033 M2 `*_HANDOFF_COLUMN_SPECS` and
  `build_*_batch_from_handoff` public aliases. Use the corresponding
  `*_ARROW_COLUMN_SPECS` constants and `build_*_batch_from_arrow` functions from
  `frtb_cva.arrow_batch`. (#474)

### Changed

- Consolidated BA-CVA citation collection into the package-local citation helper
  used by both row and batch capital assembly paths. (#719-citation-helper)
- Optimize CVA Arrow handoff and batch calculation hot spots for lower-copy
  numeric columns, non-mutating NumPy adoption, BA-CVA grouping, and SA-CVA
  risk-class routing. (#318)
- Route CVA mechanical batch array coercion helpers through `frtb-common`. (#391)
- Removed low-value CVA batch array pass-through wrappers in favor of direct common helper calls. (#402)
- Extract package-private CVA batch column coercion helpers out of `batch.py`. (#403)
- Route CVA Arrow handoff batch reads through the shared frtb-common handoff column reader. (#406)
- Delegate CVA payload hashing to `frtb_common.stable_json_hash` with compatibility tests for existing audit digests. (#538)
- Promote `frtb-cva` package metadata and maturity registry to implemented /
  validation-available for the package-owned CVA calculation scope, with expanded
  validation-pack evidence, ADR 0043, and monitoring docs. (#630)
- Delegate CVA batch column coercion helpers to shared batch array utilities. (#707)

### Documentation

- Add executable CVA notebooks covering BA-CVA, SA-CVA, mixed method, attribution, impact, and Arrow handoff usage. (#cva-notebooks)
- Add CVA regulation summary documentation, refresh regulatory assumptions to
  match the current Basel MAR50 runtime and comparison-profile boundaries, and
  move the CVA requirement registry into package-local docs. (#cva-regulation-summary)
- Audit and reconcile CVA documentation with the current partial-runtime Basel
  MAR50 support, including BA-CVA, SA-CVA, mixed carve-out, qualified-index,
  adapter, Arrow/batch, attribution, impact, and fail-closed comparison-profile
  boundaries. (#364)
- Document the `frtb-cva` implemented-scope promotion boundary and add support-matrix
  rows for out-of-scope approval and exposure/sensitivity-generation boundaries. (#627)
- Document NumPy-style docstrings for CVA handoff, payload, batch, CRIF adapter, and validation modules (issue #640). (#640)
- Document NumPy-style public API docstrings across scoped `frtb-cva` runtime modules (issue #641). (#641)

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
