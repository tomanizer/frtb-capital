# frtb-sbm detailed requirements

## Purpose

`frtb-sbm` must implement the Standardised Approach sensitivities-based method
(SBM) as an auditable capital component in the `frtb-capital` suite. It
consumes canonical sensitivity records from upstream systems or adapters,
applies regulatory risk weights and correlations, calculates bucket-level and
risk-class-level capital for delta, vega, and curvature, evaluates required
correlation scenarios, and emits frozen result records for orchestration.

The package is a capital layer only. It does not source market data, price
trades, classify raw trade economics without explicit mapping inputs, maintain
reference masters, or prepare regulatory submissions.

## Source hierarchy

Implementation must treat regulatory source text as authoritative and repository
planning documents as suite-specific build guidance.

| Priority | Source | Use |
| --- | --- | --- |
| 1 | Basel MAR20 | Standardised Approach composition and package boundary: SA = SBM + DRC + RRAO. |
| 1 | Basel MAR21 | Core SBM requirements: risk classes, delta/vega/curvature, risk weights, buckets, intra-bucket and inter-bucket aggregation, correlation scenarios. |
| 1 | U.S. NPR 2.0, section V.A.7.a | U.S. profile comparison and six-step SBM process. |
| 2 | CRR3 market-risk provisions | EU comparison profile and alternative cited bucket/weight tables where intentionally supported. |
| 3 | Current repository SBM PRD and regulatory requirements | Product scope, architecture intent, delivery slices, package boundary within this suite. |
| 3 | Existing DRC and RRAO detailed requirements | Quality bar, traceability standard, fail-closed behavior, audit/readiness expectations. |
| 4 | External/local reference implementation | Naming and decomposition inspiration only; never a substitute for citations. |

Every rule-driven quantity must have a paragraph, article, or table citation.
Do not cite only "Basel" or "U.S. NPR" when documenting a formula or lookup.

## Product boundary requirements

### SBM-BOUNDARY-001: Package responsibility

`frtb-sbm` owns non-default Standardised Approach capital from sensitivities
for:

- general interest rate risk;
- credit spread risk non-securitisation;
- credit spread risk securitisation CTP;
- credit spread risk securitisation non-CTP;
- equity risk;
- commodity risk;
- foreign exchange risk.

It must expose package-level SBM outputs only. `frtb-orchestration` owns SA
composition (SBM + DRC + RRAO), IMA fallback routing, top-of-house aggregation,
and cross-component run manifests.

### SBM-BOUNDARY-002: No sibling package imports

`frtb-sbm` may import from `frtb-common`. It must not import from `frtb-ima`,
`frtb-drc`, `frtb-rrao`, or `frtb-cva`. Any SA composition belongs in
`frtb-orchestration`.

### SBM-BOUNDARY-003: Fail-closed unsupported scope

Any requested path without cited rule mapping and deterministic test evidence
must raise an explicit unsupported-feature or input error. The package must not
emit zero, empty, or placeholder capital for unsupported risk classes, risk
measures, buckets, or profile features.

### SBM-BOUNDARY-004: Profile-driven behavior

Risk weights, bucket definitions, tenor sets, correlation parameters, scenario
labels, special-case switches, and citation metadata must come from a versioned
rule profile, not global constants embedded in kernels.

### SBM-BOUNDARY-005: Canonical-first calculation

Calculation kernels must operate on canonical typed sensitivity records.
CRIF/CSV/vendor formats may be supported through adapters, but adapters are not
part of the kernel and must preserve lineage and mapping evidence.

## Functional requirements

### SBM-FUNC-001: Public calculation entry point

The public API must accept:

- canonical `SbmSensitivity` records;
- an `SbmCalculationContext` containing run identity, scope, calculation date,
  base/reporting currency, selected rule profile, and citation policy;
- optional run controls for audit verbosity, unsupported-feature behavior, and
  scenario-detail retention.

The public API must return a frozen `SbmCapitalResult` only when all requested
features are supported and input validation passes.

### SBM-FUNC-002: Canonical sensitivity input model

The canonical input model must represent one sensitivity row before weighting
and aggregation. A record must carry, at minimum:

- stable `sensitivity_id` and `source_row_id`;
- `desk_id`, `legal_entity`, and optional `position_id`;
- `risk_class`;
- `risk_measure` (`delta`, `vega`, `curvature`);
- bucket and qualifier fields required by the selected risk class;
- risk-factor identity;
- amount and amount currency;
- tenor / option tenor / maturity fields where required;
- sign convention;
- source lineage and citation-support metadata for any mapped regulatory field.

Public boundaries may accept raw strings, but calculation kernels must receive
normalised enums and finite numeric values.

### SBM-FUNC-003: Risk class coverage

The package must support the seven SBM risk classes cited in the existing SBM
regulatory requirements and PRD. All seven must be represented in enums,
reference-data layers, validation rules, and result objects even when some
paths remain explicitly unsupported in an earlier slice.

### SBM-FUNC-004: Risk measure coverage

The package must support delta, vega, and curvature where prescribed by the
active rule profile. If a risk class or profile does not support a measure, the
package must expose that as an explicit supported/unsupported rule decision.

### SBM-FUNC-005: Rule-profile and reference-data layer

The package must expose a rule-profile layer containing:

- profile id and publication metadata;
- risk-class and risk-measure coverage flags;
- risk weights;
- bucket definitions;
- tenor sets and liquidity-horizon metadata where applicable;
- intra-bucket correlation parameters;
- inter-bucket correlation parameters;
- correlation-scenario definitions;
- special-case rules and citation ids;
- deterministic profile hashing.

Missing lookup keys must raise a package input error unless the feature is
explicitly unsupported by the active profile.

### SBM-FUNC-006: Risk-factor and bucket assignment boundary

The package must accept caller-supplied canonical bucket and risk-factor
assignment. It may offer helpers for CRIF mapping, but trade-to-risk-factor
classification remains upstream. The package must not silently infer a
regulatory bucket from incomplete free-form text.

### SBM-FUNC-007: Weighted sensitivity calculation

For each supported risk class and risk measure, the package must calculate
weighted sensitivities from canonical inputs and cited risk weights.

The result must preserve:

- raw sensitivity amount;
- selected risk weight;
- scaling inputs and outputs;
- bucket and qualifier identifiers;
- risk-measure and risk-class identity;
- lineage and citation ids.

### SBM-FUNC-008: Vega scaling

Where the active profile prescribes liquidity-horizon or tenor-based vega
scaling, the package must apply the cited formula through the reference-data
layer and preserve the unscaled and scaled values in the audit trail.

### SBM-FUNC-009: Intra-bucket aggregation

For each risk class and risk measure, the package must aggregate weighted
sensitivities within a bucket using the cited correlation structure and floors.

The intra-bucket result must preserve:

- weighted sensitivities used;
- pairwise correlation identifiers or equivalent audit evidence;
- bucket sum terms;
- bucket capital `Kb`;
- bucket-level signed aggregate `Sb` where relevant;
- floor application and reason;
- citation ids.

### SBM-FUNC-010: Inter-bucket aggregation

The package must aggregate bucket-level positions within each risk class using
the cited inter-bucket correlations and scenario adjustments.

The result must preserve:

- bucket-level inputs to inter-bucket aggregation;
- scenario-specific correlation adjustments;
- risk-class capital per scenario;
- selected/final risk-class capital under the profile rule;
- scenario selection metadata and citation ids.

### SBM-FUNC-011: Correlation scenario support

The package must support low, medium, and high correlation scenarios where the
active profile requires them. Scenario definitions must be profile-owned and
auditable. Final results must show both the scenario totals and the selected
scenario outcome.

### SBM-FUNC-012: Curvature calculation

The package must implement curvature as a separate capital path, not as a
simple reuse of delta or vega logic. Curvature inputs must carry enough
information to distinguish upward and downward shock outcomes or equivalent
canonical curvature-specific inputs required by the chosen design.

The curvature result must preserve:

- up/down scenario inputs;
- selected worst-side or profile-prescribed branch;
- curvature floors;
- bucket-level and risk-class-level curvature totals;
- explicit exclusion of unsupported shortcut behavior.

### SBM-FUNC-013: GIRR requirements

The GIRR path must support the cited GIRR bucket structure, tenor structure,
risk weights, and GIRR-specific correlation treatment from the active profile.

The GIRR design must explicitly account for profile-defined special factors such
as yield-curve tenor relationships and any prescribed inflation, basis, or
cross-currency-basis handling rather than burying them in ad hoc code paths.

### SBM-FUNC-014: CSR non-securitisation requirements

The CSR non-securitisation path must support the cited issuer/sector/rating or
equivalent regulatory bucket structure, basis distinctions where prescribed, and
measure-specific risk-weight/correlation treatment.

### SBM-FUNC-015: CSR securitisation non-CTP requirements

The CSR securitisation non-CTP path must support the cited securitisation bucket
definitions, qualifiers, and aggregation rules only when those mappings and
fixtures are complete. Until then it must fail closed.

### SBM-FUNC-016: CSR securitisation CTP requirements

The CSR securitisation CTP path must support the cited CTP-specific bucket and
aggregation rules only when those mappings and fixtures are complete. Until then
it must fail closed.

### SBM-FUNC-017: Equity requirements

The equity path must support the cited equity buckets, qualifiers, risk
weights, basis/repo distinctions where prescribed, and measure-specific
correlation treatment from the active profile.

### SBM-FUNC-018: Commodity requirements

The commodity path must support the cited commodity buckets, tenor/location
structures where prescribed, and measure-specific risk weights and
correlations.

### SBM-FUNC-019: FX requirements

The FX path must support the cited currency-bucket treatment,
reporting/base-currency logic where relevant to canonical inputs, and
risk-weight/correlation rules for supported measures.

### SBM-FUNC-020: Public result model

The result model must include, at minimum:

- total SBM capital;
- risk-class capital by scenario and final selected value;
- bucket-level capital records;
- weighted sensitivity records or equivalent explain surface;
- rule profile id and hash;
- input snapshot hash;
- supported/unsupported feature flags;
- warnings and reconciliation metadata;
- requirement ids and citation ids.

### SBM-FUNC-021: Audit and replay

Every successful capital result must carry enough metadata to reproduce the
number deterministically, including:

- package name and version;
- run id and calculation date;
- base/reporting currency;
- rule profile id, publication date, and profile hash;
- input snapshot hash;
- deterministic input count and rejected-input count;
- scenario labels;
- requirement ids and citation ids;
- stable ids for sensitivity, bucket, risk-class, and total records.

Audit serialisation must be deterministic and JSON/Markdown ready.

### SBM-FUNC-022: Explain and contribution readiness

The package must preserve stable ids, deterministic ordering, intermediate
aggregation records, and branch metadata so later analytical Euler contribution
or impact analysis can be added without breaking the public capital API.

The first capital slices do not need full Euler allocation, but they must not
block it structurally.

### SBM-FUNC-023: CRIF / adapter boundary

The package may provide CRIF-to-canonical mapping, but:

- adapters must not be required by the capital kernel;
- adapter output must be canonical `SbmSensitivity` records or package-owned
  batch objects with equivalent regulatory meaning;
- source column names, row ids, mapping warnings, and inferred-field decisions
  must be preserved;
- adapters may use Arrow at the handoff boundary under ADR 0023, but must not
  introduce dataframe execution or Arrow objects into the kernel path.

### SBM-FUNC-024: Explicit unsupported-feature reporting

Unsupported paths must identify the failing dimension explicitly, for example:

- unsupported profile;
- unsupported risk class;
- unsupported risk measure;
- missing bucket mapping;
- missing risk weight;
- missing curvature inputs;
- unsupported CRIF field convention.

## Non-functional requirements

### SBM-NFR-001: Determinism

Outputs must be deterministic for the same ordered canonical inputs, rule
profile, and code version. Grouping and serialization must use stable keys, not
incidental dictionary ordering. Determinism checks or audit controls designed to
detect bit-identical output drift must use raw numeric hashes rather than
rounding floating-point outputs, and must document the intent and any platform or
BLAS limits.

### SBM-NFR-002: Runtime dependency policy

Core runtime kernels must use Python standard library, frozen dataclasses,
enums, and package-owned `numpy` arrays where vectorisation matters. Arrow may
be used only for tabular handoff, CRIF normalization, adapters, and handoff
objects under ADR 0023; kernels must not import `pyarrow`, `pandas`, or
`polars`. Additional runtime numerical dependencies require explicit design
approval consistent with repository policy.

### SBM-NFR-003: Numeric representation

Aggregation paths should use `float64` arrays where performance matters while
preserving original input amounts in audit records. Tests must explicitly cover
sign, zero, floor, and near-zero behavior.

### SBM-NFR-004: Validation

Validation must reject:

- missing identity fields;
- unknown enum values;
- duplicate stable sensitivity ids unless an adapter explicitly aggregates rows;
- non-finite numeric amounts;
- missing source row ids;
- implicit sign conventions;
- invalid currency or tenor fields for the chosen risk class;
- incomplete curvature inputs;
- missing citation ids for rule-driven profile data;
- unsupported risk-class / risk-measure / profile combinations.

### SBM-NFR-005: Test evidence

Every implemented calculation feature must have:

- deterministic unit tests;
- invalid-input tests;
- unsupported-feature tests;
- cited fixture or hand-worked reference-vector tests;
- audit metadata and replay/hash tests.

### SBM-NFR-006: Synthetic-data-only evidence

Validation fixtures, examples, and tests must use synthetic data only.

### SBM-NFR-007: Performance target

The first production-quality aggregation slice should include a benchmark target
sufficient to show the package remains usable for large synthetic sensitivity
sets. This is an engineering control, not a regulatory requirement.

### SBM-NFR-008: Regulatory caution

No document, API, or output should present results as final regulatory capital.
Outputs remain model/engineering artifacts unless independently validated and
approved.

## Initial implementation acceptance criteria

The first capital-producing vertical slice is complete only when:

- canonical SBM sensitivities validate and normalise;
- the selected first profile contains cited bucket, weight, and correlation data
  needed by fixtures;
- weighted sensitivities, intra-bucket aggregation, inter-bucket aggregation,
  scenario handling, and total result run through one public API for the
  supported slice;
- results are frozen, serialisable, and carry rule-profile and input hashes;
- unsupported risk classes and measures fail explicitly;
- tests cover at least one positive and one negative path for validation,
  missing lookups, floors, scenario selection, and audit-hash stability.

## Recommended delivery slicing constraints

To stay aligned with the existing PRD and repository style, issue breakdown
should follow these constraints:

- Skeleton and traceability first.
- Canonical data model and profile layer before risk-class logic.
- Shared aggregation engine before multiple risk classes.
- One thin end-to-end vertical slice early.
- Curvature as a distinct later slice.
- CRIF adapters after canonical runtime exists.
- Audit/replay before orchestration integration.

## Gaps this document closes vs the current SBM docs

The current SBM PRD and regulatory requirements are a strong start, but they
are still missing the same level of issue-ready detail that DRC has. This draft
adds:

- explicit package boundary rules;
- canonical input and public result requirements;
- profile-layer requirements;
- risk-class-specific functional requirements;
- fail-closed unsupported behavior;
- audit, replay, and attribution-readiness requirements;
- non-functional and validation requirements;
- issue-friendly requirement IDs.
