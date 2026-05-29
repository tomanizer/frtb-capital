# frtb-rrao decisions and implementation plan

This document is the historical v1 implementation plan. The scoped
canonical-input calculation path is now implemented; remaining questions below
describe future cross-package design choices, not blockers for current RRAO v1
mechanics.

## Decision log

### RRAO-DEC-001: Implement U.S. NPR and Basel canonical-input slice first

**Decision:** The first capital-producing implementation slice will support
canonical residual-risk positions for the U.S. NPR 2.0 proposed section
`__.211` profile and Basel MAR23 profile, with classification evidence supplied
explicitly by the input.

**Reason:** RRAO formula mechanics are simple, but classification is the risk.
Starting with canonical, evidence-backed inputs provides a useful capital chain
without prematurely implementing trade-text parsing or all jurisdictional
classification variants.

**Implication:** PRA paths and unmapped EU-specific features must raise explicit
unsupported-feature errors until their source mappings and fixture packs are
complete.

### RRAO-DEC-002: Keep data contracts package-local initially

**Decision:** RRAO-specific dataclasses, enums, and citations start in
`frtb_rrao.data_models`.

**Reason:** `frtb-common` should not absorb RRAO-specific evidence and
exclusion concepts before SBM, DRC, and CVA contract shapes are stable.

**Implication:** Only truly shared primitives, such as unsupported-feature
exceptions and future generic rule-profile identity, should move to
`frtb-common` under a separate cross-cutting issue and ADR if needed.

### RRAO-DEC-003: Profiles own parameters; kernels receive typed values

**Decision:** Classification labels, exclusion support, risk weights, and
citation ids belong in versioned rule profiles and reference-data helpers.
Calculation kernels receive typed decisions and do not branch on global regime
names.

**Reason:** This matches the suite documentation pattern and keeps regulatory
traceability and reproducibility separate from numeric code.

**Implication:** Tests must cover profile lookup separately from calculations.

### RRAO-DEC-004: Classification evidence is explicit

**Decision:** `RraoEvidenceType` and evidence labels are required after adapter
normalisation. Kernels must not infer classification from free-form trade text.

**Reason:** Basel MAR23 and proposed U.S. section `__.211` are classification
rules, not text-mining instructions. A capital layer should be auditable and
deterministic.

**Implication:** CRIF/vendor adapters must map source conventions into explicit
evidence and record the mapping in lineage.

### RRAO-DEC-005: Store excluded positions as zero-capital lines

**Decision:** Successful exclusions are represented as frozen line records with
zero add-on, explicit exclusion reason, and citations.

**Reason:** Exclusions are part of the capital result's audit story. Dropping
excluded rows would make reconciliation and review harder.

**Implication:** Capital totals sum only included line add-ons, while audit
counts and explain subtotals include excluded lines.

### RRAO-DEC-006: No offsetting or diversification

**Decision:** The initial total RRAO result is the simple sum of weighted gross
effective notionals for included positions.

**Reason:** Basel MAR23.8 and proposed U.S. section `__.211(c)` prescribe a
simple sum. The cited exclusions do not create general netting, diversification,
or hedge-benefit mechanics.

**Implication:** Any future profile with a different aggregation treatment must
cite the rule and add tests before changing this behavior.

### RRAO-DEC-007: Additive explain before advanced allocation

**Decision:** The first implementation will provide line and subtotal explain
records. Advanced allocation views may be added after the public API is stable.

**Reason:** RRAO is additive, so line contribution is already exact. The package
first needs stable capital and audit chains.

**Implication:** Issue #94 added additive allocation helpers after the public
API, audit, and fixtures were in place.

### RRAO-DEC-008: External GitHub implementations inform adapters, not rules

**Decision:** Public implementations such as `frtb-net/FRTB` can inform
adapter-field naming and explain-output shape, but the package must not copy
code or adopt implementation-specific formula extensions.

**Reason:** Regulatory source text is authoritative. Some public examples use
stateful dataframe designs or non-regulatory risk multipliers that would violate
the suite's clarity and dependency rules.

**Implication:** The implementation should keep standard-library adapters and
pure calculation kernels.

## Implemented sequence

1. Completed scaffold and explicit failure paths.
2. Added RRAO architecture, detailed requirements, and actionable issue plan.
3. Added RRAO package model documentation and traceability skeleton.
4. Implemented data models and validation.
5. Implemented rule profiles and reference data for U.S. NPR 2.0 and Basel MAR23
   canonical-input slice.
6. Implemented classification and exclusion decisions.
7. Implemented line add-ons, subtotals, and total capital.
8. Added public run API and audit/replay artifacts.
9. Added synthetic validation fixture pack.
10. Added optional CRIF/FNet adapter.
11. Added EU CRR3 profile mapping and fixtures.
12. Integrated RRAO package output contract into orchestration, without changing
    SA composition until SBM and DRC outputs are compatible.
13. Added performance and replay controls.
14. Added additive allocation/reporting helpers.
15. Added exact back-to-back match-group validation, external comparator tests,
    property tests, mutation evidence, a narrow public API contract, and shared
    reconciliation tolerance helpers.

## Documentation deliverables

Each implementation slice must update:

- `docs/modules/frtb-rrao/DETAILED_REQUIREMENTS.md`;
- `docs/modules/frtb-rrao/REGULATORY_REQUIREMENTS.md`;
- `docs/modules/frtb-rrao/requirements/BASEL_FRTB_RRAO.yml`;
- `packages/frtb-rrao/README.md`;
- package-local regulatory traceability once calculation modules exist;
- validation fixtures and audit reports when result formats change.

## First vertical slice target

The first useful release of `frtb-rrao` is a U.S. NPR 2.0 / Basel MAR23
canonical-input slice:

- canonical positions;
- cited classification evidence;
- cited exclusion handling;
- 1.0% exotic risk weight;
- 0.1% other residual-risk weight;
- supervisor-directed inclusion;
- simple additive total;
- deterministic line and subtotal explain records;
- frozen public result with rule-profile and input hashes.

This is narrow enough to implement and review, but broad enough to exercise the
core RRAO mechanics.

## Remaining design questions

1. Should `RraoRuleProfile` remain package-local for RRAO v1 or move to
   `frtb-common` after DRC and RRAO both have stable profile contracts?
2. Should gross effective notional remain `float` throughout kernels or should
   adapters preserve `Decimal` amounts for audit while kernels receive floats?
3. Resolved in issue #90: the first U.S. NPR slice implements proposed section
   `__.211(a)(3)` only when an explicit `__.205(e)(3)(iii)` investment-fund
   descriptor and cited mandate evidence are supplied.
4. Resolved in issue #89: CRIF/FNet mapping shipped after the first
   canonical-input capital slice as an optional adapter.
5. Resolved in issue #93: the benchmark fixture uses 100,000 deterministic
   synthetic positions and records replay hashes.

The unresolved items are cross-package contract choices and do not block scoped
v1 RRAO calculation for supported canonical inputs.
