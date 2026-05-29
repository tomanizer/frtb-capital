# frtb-rrao detailed requirements

## Purpose

`frtb-rrao` must implement the Standardised Approach residual risk add-on
(RRAO) as an auditable capital component in the `frtb-capital` suite. It
consumes canonical residual-risk position records from upstream risk systems or
adapters, classifies each position as exotic, other residual risk, explicitly
excluded, supervisor-directed, or unsupported, and calculates the additive
notional-based add-on for supported positions.

The package is a capital layer. It does not price products, infer legal trade
classification from free-form descriptions, source market data, perform
sensitivities calculations, or compose the full Standardised Approach total.

## Source hierarchy

The implementation must treat regulatory source text as authoritative and
external implementations as design inspiration only.

| Priority | Source | Use |
| --- | --- | --- |
| 1 | [Basel MAR23](https://www.bis.org/basel_framework/chapter/MAR/23.htm) | RRAO scope, exotic and other residual-risk split, exclusions, back-to-back treatment, and 1.0% / 0.1% formula. |
| 1 | [Basel MAR20](https://www.bis.org/basel_framework/chapter/MAR/20.htm) | Standardised Approach composition: SA = SBM + DRC + RRAO. |
| 1 | [U.S. NPR 2.0, 91 FR 14952](https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959) | Proposed U.S. residual risk add-on, including proposed section `__.211` and narrative section V.A.7.b. |
| 2 | [Regulation (EU) No 575/2013 Article 325u](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02013R0575-20240709) and [Commission Delegated Regulation (EU) 2022/2328](https://eur-lex.europa.eu/eli/reg_del/2022/2328/oj/eng) | EU comparison profile for exotic underlyings, residual-risk instrument lists, and non-presumptive risks. |
| 2 | [EBA RTS on residual risk add-on](https://www.eba.europa.eu/legacy/regulation-and-policy/regulatory-activities/market-counterparty-and-cva-risk/regulatory-2?version=2021) | Background for EU RTS scope and classification rationale. |
| 3 | Public GitHub reference implementations such as [`frtb-net/FRTB` `SA_RRAO_Calc.py`](https://github.com/frtb-net/FRTB/blob/bdce773dc01868f61d8fdd65476c52193a2321e1/SA_RRAO_Calc.py) and [`FNet_Format_Documentation.md`](https://github.com/frtb-net/FRTB/blob/bdce773dc01868f61d8fdd65476c52193a2321e1/FNet_Format_Documentation.md) | Input naming and explain-output inspiration only. Do not copy code or treat implementation choices as regulatory requirements. |
| 3 | [OCC PDF copy of 91 FR 14952](https://www.occ.gov/news-issuances/federal-register/2026/91fr14952.pdf) | Convenience copy for page-specific review. GovInfo remains the primary source. |

Every risk weight, classification reason, exclusion reason, and profile support
switch must have a paragraph, proposed-section, article, or table citation. Do
not cite a framework name alone when documenting a calculation.

## Product boundary requirements

### RRAO-BOUNDARY-001: Package responsibility

`frtb-rrao` owns RRAO capital for:

- market risk covered positions with exotic exposures;
- market risk covered positions with other residual risks;
- supervisor-directed inclusion where the selected rule profile permits it;
- explicit exclusions and zero-capital outcomes where the selected rule profile
  permits them.

It must expose package-level RRAO outputs only. `frtb-orchestration` owns SA
composition (`SBM + DRC + RRAO`), IMA fallback routing, top-of-house
aggregation, and cross-component run manifests.

### RRAO-BOUNDARY-002: No sibling package imports

`frtb-rrao` may import from `frtb-common`. It must not import from `frtb-ima`,
`frtb-sbm`, `frtb-drc`, or `frtb-cva`. Any cross-component aggregation belongs
in `frtb-orchestration`.

### RRAO-BOUNDARY-003: Classification evidence is input, not inferred text

The calculation layer must not infer exotic or other residual-risk treatment
from free-form trade descriptions. Adapter boundaries may map source fields into
canonical enums, but capital kernels must receive explicit classification
evidence, source lineage, and citation ids.

### RRAO-BOUNDARY-004: Fail-closed unsupported scope

Any requested path that lacks a cited rule mapping and deterministic tests must
raise an explicit `UnsupportedRegulatoryFeatureError` or package-specific input
error. The package must never return successful placeholder capital.

## Functional requirements

### RRAO-FUNC-001: Public calculation entry point

The public API must accept:

- canonical `RraoPosition` records;
- an `RraoCalculationContext` containing run identity, desk/legal-entity scope,
  calculation date, base currency, selected rule profile, and citation policy;
- optional run controls for audit verbosity and unsupported-feature behavior.

The API must return a frozen `RraoCapitalResult` only when all requested
features are supported and all input validation passes.

### RRAO-FUNC-002: Canonical input model

The canonical input model must represent one residual-risk position row before
calculation. A record must carry:

- stable `position_id`, `source_row_id`, `desk_id`, and `legal_entity`;
- `residual_risk_type`: exotic, other residual risk, explicit exclusion,
  supervisor-directed, or unsupported;
- classification evidence: evidence type, evidence label, rule bucket, and
  optional supervisor directive id;
- gross effective notional, currency, and reporting notional source;
- exclusion indicators for listed, CCP/QCCP clearable, non-path-dependent
  option with two or fewer underlyings, exact third-party back-to-back trade,
  deliverable hedge pair, government/GSE debt, fallback-capital treatment,
  internal desk transaction, and agency-determined exclusion;
- product descriptors needed for classification audit, including underlying
  count, path-dependency flag, embedded option metadata, maturity/strike/barrier
  availability, multiple strike/barrier flag, investment fund flag, and CTP
  hedge flag where supplied;
- source lineage and citation identifiers for every mapped regulatory field.

Inputs may accept raw strings at adapter boundaries, but calculation kernels
must receive normalised enums and finite numeric values.

### RRAO-FUNC-003: Gross effective notional sign convention

RRAO is calculated on gross effective notional. The package must reject negative
notional inputs after adapter normalisation unless the adapter explicitly
normalises a signed source amount into an absolute gross effective notional and
records the source convention in lineage.

Proposed U.S. section `__.211(c)(2)` anchors gross effective notional to the
notional amount reported in the most recent Call Report or FR Y-9C for the U.S.
profile. Basel MAR23.8 anchors gross notional for the Basel profile.

### RRAO-FUNC-004: Exotic exposure classification

The U.S. NPR 2.0 profile must classify proposed section `__.211(a)(1)`
positions as exotic exposure when the position has an exotic exposure. The
first fixture set must include longevity, weather, and natural disaster examples
from narrative section V.A.7.b.i and Basel MAR23.3 examples.

The EU comparison profile must be able to represent Article 1 of Delegated
Regulation (EU) 2022/2328, which specifies longevity risk, weather, natural
disasters, and future realised volatility as exotic underlyings, but may remain
unsupported for capital until the EU profile has full fixture coverage.

### RRAO-FUNC-005: Other residual-risk classification

The U.S. NPR 2.0 profile must classify proposed section `__.211(a)(2)` positions
as other residual risk when they are:

- CTP positions with three or more underlying exposures, except hedges of CTP
  positions;
- positions subject to curvature or vega capital requirements with payoffs that
  cannot be replicated as a finite linear combination of vanilla options or the
  underlying instrument, subject to the proposed section's curvature exception;
- options or embedded options with no maturity;
- options or embedded options with no strike price or barrier;
- options or embedded options with multiple strike prices or barriers.

The narrative section V.A.7.b.i identifies gap risk, correlation risk, and
behavioural risk such as prepayments as other residual-risk examples. These
examples must be represented as evidence categories, not as uncited formula
changes.

### RRAO-FUNC-006: Investment fund inclusion

The U.S. NPR 2.0 profile must represent proposed section `__.211(a)(3)`, which
includes the portion of the exposure amount from an equity position in an
investment fund required under proposed section `__.205(e)(3)(iii)`.

This path requires an explicit investment-fund descriptor carrying the
proposed section `__.205(e)(3)(iii)` backstop-method linkage, mandate evidence,
and included exposure portion. It must not be silently treated as generic other
residual risk.

### RRAO-FUNC-007: Supervisor-directed inclusion

The policy layer must allow supervisor-directed inclusion for proposed section
`__.211(a)(4)` positions, where the agency determines RRAO is required to
capture material risks. The input must carry a directive id or evidence note.

Supervisor-directed inclusion must never be inferred from product type alone.

### RRAO-FUNC-008: Exclusion handling

The U.S. NPR 2.0 profile must support explicit exclusion logic for proposed
section `__.211(b)`:

- listed positions, CCP-cleared-eligible positions, and options without
  path-dependent payoffs or with two or fewer underlyings may be excluded from
  other residual-risk treatment under proposed section `__.211(b)(1)`;
- exact third-party back-to-back transactions may be excluded under proposed
  section `__.211(b)(2)(i)`;
- deliverable hedge pairs may be excluded under proposed section
  `__.211(b)(2)(ii)`;
- U.S. government securities or GSE debt may be excluded under proposed section
  `__.211(b)(2)(iii)`;
- fallback-capital positions may be excluded under proposed section
  `__.211(b)(2)(iv)`;
- qualifying internal desk transactions may be excluded under proposed section
  `__.211(b)(2)(v)`;
- agency-determined exclusions may be represented under proposed section
  `__.211(b)(2)(vi)`.

Exclusions and zero-capital outcomes are successful only when explicitly cited
and recorded in result lines.

### RRAO-FUNC-009: Back-to-back matching

Exact third-party back-to-back exclusion requires a deterministic match group.
The package must validate the group contains the referenced transactions, record
the matching evidence id, and emit excluded line records for both transactions.

If matching evidence is absent, the input must remain subject to normal
classification or fail validation.

### RRAO-FUNC-010: Risk weights

The first U.S. NPR 2.0 and Basel profile mappings must include:

- 1.0% for exotic exposures, anchored to Basel MAR23.8(2)(a) and proposed
  section `__.211(c)(1)(i)`;
- 0.1% for other residual risks, anchored to Basel MAR23.8(2)(b) and proposed
  section `__.211(c)(1)(ii)`;
- 0.0% for cited exclusions, stored as excluded line records rather than as
  unsupported or missing inputs.

Missing risk-weight lookup keys must raise a package input error unless the
profile explicitly marks the feature unsupported.

### RRAO-FUNC-011: Additive capital calculation

For each included position, the line add-on equals:

```text
gross_effective_notional * risk_weight
```

Total RRAO equals the simple sum of included line add-ons. No diversification,
hedge benefit, correlation aggregation, scenario aggregation, maturity scaling,
or offsetting is recognised unless a future profile cites and tests a different
treatment.

### RRAO-FUNC-012: Bucket and explain aggregation

The package must expose deterministic subtotals by:

- classification: exotic, other residual risk, supervisor-directed, excluded,
  unsupported rejected input;
- evidence type, such as exotic underlying, gap risk, correlation risk,
  behavioural risk, no-maturity optionality, no-strike/barrier optionality, or
  multiple-strike/barrier optionality;
- desk id and legal entity where supplied.

These subtotals are explain views only. They must reconcile to line add-ons and
must not change the capital number.

### RRAO-FUNC-013: CRIF and adapter boundary

`frtb-rrao` may provide a CRIF-to-canonical adapter, but adapters must not be
part of calculation kernels. Adapter output must be canonical `RraoPosition`
records. The adapter must record source column names, source row ids, mapping
warnings, and any regulatory field inferred from non-regulatory input labels.

Public GitHub FNet examples map `RRAO_1_PERCENT` and `RRAO_01_PERCENT` to
exotic and non-exotic buckets with notional amounts. This is useful adapter
context only; the package API must preserve richer regulatory evidence than a
two-bucket calculator.

### RRAO-FUNC-014: Audit and replay

Every capital-producing result must carry:

- package name and version;
- code version where available;
- run id, calculation date, and base currency;
- rule profile id, source publication date, and profile hash;
- input snapshot hash;
- deterministic input count, included count, excluded count, and rejected count;
- requirement ids and citation ids;
- line contributions, exclusion records, by-classification subtotals, and total
  RRAO sufficient to reproduce the capital number.

Audit serialization must be JSON/Markdown ready and deterministic.

### RRAO-FUNC-015: Explain and allocation output

Because RRAO is additive, line contribution equals the weighted notional add-on.
The package must expose line-level contribution records in the first
capital-producing slice. Any later allocation view must reconcile exactly to
total RRAO and must not change capital.

## Non-functional requirements

### RRAO-NFR-001: Determinism

Outputs must be deterministic for the same ordered canonical inputs, rule
profile, and code version. Where grouping is required, output ordering must use
stable keys rather than dictionary insertion side effects.

### RRAO-NFR-002: Runtime dependency policy

Runtime kernels must use Python standard-library types, frozen dataclasses,
enums, and `numpy` only where vectorisation is useful. `pandas`, `polars`,
`scipy`, and `statsmodels` may be used in tests, notebooks, validation,
research, or optional adapters only when they do not leak into the core runtime
path. Any new runtime dependency requires an ADR under ADR 0011.

### RRAO-NFR-003: Numeric representation

The kernel should use finite `float` values for gross effective notional and
line add-ons, preserving original source amounts in audit records. Tests must
cover zero, near-zero, very large notional, and invalid numeric behavior
explicitly. If exact decimal rounding becomes a regulatory requirement, it
requires a focused design decision before implementation.

### RRAO-NFR-004: Validation

Validation must reject:

- missing identity fields;
- unknown enum values;
- duplicate position ids unless the adapter explicitly aggregates source rows;
- non-finite gross effective notional;
- negative gross effective notional after normalisation;
- missing source row ids;
- missing classification evidence for included positions;
- unsupported category/profile combinations;
- missing citation ids for rule-driven fields;
- exclusion flags without the required evidence ids.

### RRAO-NFR-005: Test evidence

Every calculation feature must have:

- deterministic unit tests;
- invalid-input tests;
- unsupported-feature tests;
- cited hand-calculated fixture tests;
- audit-metadata tests;
- replay/hash tests where the feature contributes to public capital.

### RRAO-NFR-006: Performance target

The first implemented path should include a benchmark target for at least
100,000 synthetic residual-risk positions across multiple desks, legal
entities, classifications, and exclusion reasons. The target is an engineering
control for suite usability, not a regulatory requirement.

## Initial implementation acceptance criteria

The first capital-producing vertical slice is complete only when:

- canonical residual-risk positions validate and normalise;
- U.S. NPR 2.0 profile contains cited classification, exclusion, risk-weight,
  and gross effective notional mappings needed by fixtures;
- Basel profile contains cited MAR23 risk weights and can calculate the same
  canonical included/excluded fixture where classification evidence is supplied;
- EU/PRA profile gaps raise explicit unsupported-feature errors;
- line add-ons, subtotals, and total RRAO run through one public API;
- results are frozen, serialisable, and carry rule-profile/input hashes;
- tests cover exotic, other residual risk, supervisor-directed inclusion,
  explicit exclusions, back-to-back exclusion, invalid notional, missing
  evidence, unsupported profile paths, and audit hash stability.
