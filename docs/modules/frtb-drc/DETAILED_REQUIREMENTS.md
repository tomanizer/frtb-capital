# frtb-drc detailed requirements

## Purpose

`frtb-drc` must implement the Standardised Approach default risk charge (DRC)
as an auditable capital component in the `frtb-capital` suite. It consumes
canonical default-risk exposure records from upstream risk systems or adapters,
calculates gross jump-to-default (JTD), permitted net JTD, bucket capital, and
category-level DRC, and emits frozen result records for orchestration.

The package is a capital layer. It does not source market data, master issuer
reference data, value trades, generate P&L, or prepare regulatory submissions.

## Source hierarchy

The implementation must treat regulatory source text as authoritative and the
external reference implementation as design inspiration only.

| Priority | Source | Use |
| --- | --- | --- |
| 1 | [Basel MAR22](https://www.bis.org/basel_framework/chapter/MAR/22.htm) | Default-risk category structure, JTD, offsetting, hedge benefit ratio, risk weights, securitisation non-CTP, and CTP rules. |
| 1 | [Basel MAR20](https://www.bis.org/basel_framework/chapter/MAR/20.htm) | Standardised Approach composition: SA = SBM + DRC + RRAO. |
| 1 | [U.S. NPR 2.0, 91 FR 14952](https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959) | Proposed U.S. default risk capital requirement, including proposed section `__.210` mechanics. |
| 2 | [CRR3 Regulation (EU) 2024/1623](https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng) and EBA single-rulebook pages such as [Article 325w](https://www.eba.europa.eu/regulation-and-policy/single-rulebook/interactive-single-rulebook/12175) | EU comparison profile, Article 325w gross JTD and related Articles 325x-325ad. |
| 3 | External `extract_cva` capital navigator DRC component | Naming, workflow, CRIF mapping, and explain-output inspiration. Not a regulatory source. |

Every threshold, risk weight, LGD value, bucket definition, maturity rule, and
offsetting rule must have a paragraph, proposed-section, article, or table
citation. Do not cite a framework name alone when documenting a calculation.

## Product boundary requirements

### DRC-BOUNDARY-001: Package responsibility

`frtb-drc` owns DRC capital for:

- non-securitisation debt and equity default-risk positions;
- securitisation positions non-CTP;
- correlation trading portfolio (CTP) default-risk positions.

It must expose package-level DRC outputs only. `frtb-orchestration` owns SA
composition (`SBM + DRC + RRAO`), IMA fallback routing, top-of-house
aggregation, and cross-component run manifests.

### DRC-BOUNDARY-002: No sibling package imports

`frtb-drc` may import from `frtb-common`. It must not import from `frtb-ima`,
`frtb-sbm`, `frtb-rrao`, or `frtb-cva`. Any cross-component aggregation belongs
in `frtb-orchestration`.

### DRC-BOUNDARY-003: Fail-closed unsupported scope

Any requested path that lacks a cited rule mapping and deterministic tests must
raise an explicit `UnsupportedRegulatoryFeatureError` or package-specific input
error. The package must never return zero, empty, or successful placeholder
capital.

## Functional requirements

### DRC-FUNC-001: Public calculation entry point

The public API must accept:

- canonical `DrcPosition` records;
- a `DrcCalculationContext` containing run identity, desk/legal-entity scope,
  calculation date, base currency, selected rule profile, and citation policy;
- optional run controls for audit verbosity and unsupported-feature behavior.

The API must return a frozen `DrcCapitalResult` only when all requested features
are supported and all input validation passes.

### DRC-FUNC-002: Canonical input model

The canonical input model must represent one default-risk exposure row before
calculation. A record must carry:

- stable `position_id`, `source_row_id`, `desk_id`, and `legal_entity`;
- `risk_class`: non-securitisation, securitisation non-CTP, or CTP;
- `issuer_id` for obligor-based paths and `tranche_id` / `index_series_id` for
  tranche or CTP paths;
- instrument type and default direction;
- seniority or tranche attachment/detachment metadata as applicable;
- credit quality or rating mapping inputs;
- bucket assignment inputs, including sector, region, sovereign/PSE/GSE flags,
  and defaulted status;
- notional or face amount, market value where required, cumulative P&L where
  required, maturity, and currency;
- LGD category or explicit cited LGD override where the rule profile permits it;
- source lineage and citation identifiers for every mapped regulatory field.

Inputs may accept raw strings at adapter boundaries, but calculation kernels
must receive normalised enums and finite numeric values.

### DRC-FUNC-003: Sign convention

The package must distinguish accounting buy/sell sign from default-risk
direction. A position is long default risk when issuer default produces a loss
and short default risk when issuer default produces a gain. This is required by
Basel MAR22.10 and proposed U.S. section `__.210(b)(1)(ii)`.

### DRC-FUNC-004: Gross JTD

For non-securitisation debt and equity positions, gross default exposure must
be calculated from cited rule-profile inputs: LGD rate, notional or face amount,
and the recognised P&L or market-value adjustment. Proposed U.S. section
`__.210(b)(1)(iii)-(vii)` and Basel MAR22.9-MAR22.12 are the first regulatory
anchors.

The gross JTD result must preserve:

- raw notional or face amount;
- recognised P&L / market-value adjustment;
- selected LGD rate and LGD source;
- default direction;
- gross JTD before maturity scaling;
- source row lineage;
- citation ids.

### DRC-FUNC-005: LGD reference data

The U.S. NPR 2.0 profile must include the proposed LGD values in section
`__.210(b)(1)(iv)`:

- 100% for equity, non-senior debt, and defaulted positions;
- 75% for senior debt unless a lower LGD is assigned;
- 75% for GSE debt issued but not guaranteed by GSEs;
- 50% for positions in U.S. PSEs;
- 25% for GSE-guaranteed debt;
- 25% for covered bonds;
- 0% where value is not linked to issuer recovery.

Basel, CRR3, and PRA profiles must expose their own cited LGD tables or raise
unsupported-feature errors until those tables are mapped.

### DRC-FUNC-006: Maturity scaling

The package must apply the profile's maturity weighting before permitted
offsetting. Proposed U.S. section `__.210(a)(2)(iii)(A)-(B)` requires scaling
for maturities below one year, a three-month floor for maturities below three
months, no scaling for maturities of one year or greater, and derivative hedge
maturity treatment based on the derivative contract where applicable.

The audit trail must retain both unscaled and scaled amounts.

### DRC-FUNC-007: Non-securitisation netting

For non-securitisation positions, the package must net long and short gross
default exposures only to the same obligor and only where seniority and maturity
rules permit. Proposed U.S. section `__.210(b)(2)` permits offsetting where the
short gross default exposure has the same or lower seniority relative to the
long gross default exposure, subject to maturity weighting and guarantor rules.

The netting output must identify:

- netting group key;
- included position ids;
- seniority ordering used;
- unscaled and scaled long/short totals;
- final net JTD direction and amount;
- any rejected offset pair with reason code.

### DRC-FUNC-008: Bucket assignment

Every position must be assigned to exactly one DRC category and one bucket
within that category before capital aggregation. The U.S. NPR non-securitisation
profile must support the proposed section `__.210(b)(3)(i)` buckets:

- non-U.S. sovereign exposures;
- PSE and GSE debt positions;
- corporate positions;
- defaulted positions.

The U.S. NPR profile must not add a separate U.S. sovereign, specified
supranational, MDB, municipal, or local-government default-risk bucket unless a
future cited rule profile defines one. Inputs carrying those labels as
`bucket_key` values must be rejected before capital calculation. Municipal or
local-government debt may enter this profile only through a cited upstream
classification to the PSE/GSE debt bucket when that treatment is valid.

Securitisation non-CTP and CTP bucket assignment must be implemented only after
their cited bucket dimensions, "other" bucket handling, and fixture coverage are
complete.

### DRC-FUNC-009: Risk weights

Risk weights must be looked up from the selected versioned rule profile. The
lookup key must be explicit and auditable: category, bucket, credit quality or
rating grade, defaulted status, securitisation treatment, and profile id.

For the U.S. NPR 2.0 non-securitisation profile, `UNRATED` is an input
classification sentinel only. Proposed Table 1 to section `__.210` assigns
non-defaulted risk weights by investment grade, speculative grade, and
sub-speculative grade credit-quality categories, plus a separate defaulted
bucket. Inputs carrying `UNRATED` must be mapped upstream to a cited chargeable
category or rejected before capital calculation; the package must not silently
default unrated exposures to another tier.

Missing risk weights must be input errors unless the profile explicitly marks
the feature unsupported.

### DRC-FUNC-010: Hedge benefit ratio

For each bucket, the package must calculate the hedge benefit ratio (HBR) from
aggregate net long and net short default exposures using the selected profile's
cited formula. Proposed U.S. section `__.210(a)(2)(iv)(A)` anchors the HBR
inputs for the U.S. profile.

The result must preserve aggregate long, aggregate short, denominator, computed
ratio, floor/cap behavior, and citation ids.

### DRC-FUNC-011: Bucket capital

For each bucket, capital must be calculated from risk-weighted obligor or
tranche-level net JTD exposures and the HBR under the cited category formula.
Bucket capital must retain:

- net long and net short totals;
- risk-weighted long and short components;
- HBR;
- floor application;
- bucket total;
- position or netting-group contributions where supported.

### DRC-FUNC-012: Category aggregation

The total for non-securitisation and securitisation non-CTP categories must be
the sum of bucket-level default risk capital requirements. CTP must use the
profile-specific CTP aggregation formula. Proposed U.S. section
`__.210(a)(4)` prohibits diversification benefits across default-risk
categories; therefore the overall DRC result must sum category totals unless a
different profile explicitly requires and cites another treatment.

### DRC-FUNC-013: Securitisation non-CTP path

The securitisation non-CTP path must fail closed until the package implements:

- tranche identity, attachment point, detachment point, maturity, fair value,
  and underlying pool descriptors;
- bucket assignment by asset class and region where required;
- "other" bucket fallback with explicit citation;
- long/short offsetting only where the cited replication and decomposition
  rules permit it;
- securitisation risk weights mapped to the relevant banking-book treatment;
- fair-value cap where the selected profile permits it.

Proposed U.S. section `__.210(c)` and Basel MAR22.27-MAR22.38 are the first
anchors.

### DRC-FUNC-014: CTP path

The CTP path must fail closed until it supports:

- CTP portfolio membership evidence;
- index, series, tranche, and residual component identity;
- decomposition or replication rules for long/short tranche combinations;
- CTP-specific HBR;
- CTP-specific bucket and final category aggregation.

Proposed U.S. section `__.210(d)` and Basel MAR22.39-MAR22.47 are the first
anchors.

### DRC-FUNC-015: CRIF and adapter boundary

`frtb-drc` may provide a CRIF-to-canonical adapter, but adapters must not be
part of calculation kernels. Adapter output must be canonical `DrcPosition`
records. The adapter must record source column names, source row ids, mapping
warnings, and any regulatory field inferred from non-regulatory input labels.

### DRC-FUNC-016: Audit and replay

Every capital-producing result must carry:

- package name and version;
- code version where available;
- run id, calculation date, and base currency;
- rule profile id, source publication date, and profile hash;
- input snapshot hash;
- deterministic input count and rejected-input count;
- requirement ids and citation ids;
- gross JTD, scaled JTD, net JTD, HBR, risk-weight, bucket, category, and total
  records sufficient to reproduce the capital number.
- lineage and branch metadata sufficient to add analytical Euler or
  finite-difference impact in a later slice without changing the capital
  calculation API.

Audit serialization must be JSON/Markdown ready and deterministic.

### DRC-FUNC-017: Explain and contribution output

The package must expose explain records at bucket and netting-group level in
the first non-securitisation slice. The first capital-producing slice does not
need to calculate analytical Euler contribution, but it must preserve the audit
lineage and branch metadata required by
[ADR 0012](../../decisions/0012-capital-impact-attribution.md).

Future attribution output must:

- distinguish analytical Euler contribution from baseline-vs-candidate impact;
- identify source level, source id, bucket, category, method, contribution,
  marginal multiplier, and residual;
- reconcile to bucket, category, and total capital where the active branch
  permits exact reconciliation;
- report explicit residuals or unsupported attribution where floors, zero
  denominators, bucket moves, category moves, or unsupported features prevent
  exact Euler decomposition.

For non-securitisation DRC, analytical Euler is the preferred method for stable
bucket-capital branches after netting. Finite-difference impact is acceptable
only when labelled as an impact method rather than a marginal contribution.

### DRC-FUNC-018: Change impact assessment

The package must be structured so a later `impact.py` module can compare a
baseline `DrcCapitalResult` with a candidate `DrcCapitalResult` and explain
capital deltas by stable ids. The first implementation must therefore retain
stable ids and deterministic ordering across position, gross JTD, scaled JTD,
netting group, bucket, category, and total records.

Impact records are not regulatory capital outputs. They are explainability and
change-control artifacts, and must not change the capital number.

## Non-functional requirements

### DRC-NFR-001: Determinism

Outputs must be deterministic for the same ordered canonical inputs, rule
profile, and code version. Where grouping is required, output ordering must use
stable keys rather than dictionary insertion side effects.

### DRC-NFR-002: Runtime dependency policy

Runtime kernels must use Python standard-library types, frozen dataclasses,
enums, and package-owned `numpy` arrays where vectorisation is useful. Arrow may
be used only for tabular handoff, CRIF normalization, adapters, and handoff
objects under ADR 0023. `pandas`, `polars`, `scipy`, and `statsmodels` may be
used in tests, notebooks, validation, research, or optional adapters only when
they do not leak into the core runtime path. Kernels must not import `pyarrow`,
`pandas`, or `polars`. Any new runtime dependency beyond the approved Arrow
handoff boundary requires an ADR under ADR 0011.

### DRC-NFR-003: Numeric representation

The kernel should use `float64` arrays for aggregation and preserve original
input amounts in audit records. Tests must cover sign, zero, floor, and
near-zero behavior explicitly. If exact decimal rounding becomes a regulatory
requirement, it requires a focused design decision before implementation.

### DRC-NFR-004: Validation

Validation must reject:

- missing identity fields;
- unknown enum values;
- duplicate position ids unless the adapter explicitly aggregates source rows;
- non-finite numeric amounts;
- negative maturities;
- missing source row ids;
- implicit sign conventions;
- unsupported category/profile combinations;
- missing citation ids for rule-driven fields.

### DRC-NFR-005: Test evidence

Every calculation feature must have:

- deterministic unit tests;
- invalid-input tests;
- unsupported-feature tests;
- cited reference-vector or hand-calculated fixture tests;
- audit-metadata tests;
- replay/hash tests where the feature contributes to public capital.

### DRC-NFR-006: Performance target

The first implemented non-securitisation path should include a benchmark target
for at least 100,000 synthetic positions across 1,000 issuers, four buckets,
multiple desks, and long/short offsetting. The target is not a regulatory
requirement; it is an engineering control to keep the package usable for suite
examples and future validation notebooks.

## Initial implementation acceptance criteria

The first capital-producing vertical slice is complete only when:

- non-securitisation canonical positions validate and normalise;
- U.S. NPR 2.0 profile contains cited LGD, bucket, maturity, HBR, and risk
  weight mappings needed by the fixtures;
- gross JTD, maturity scaling, same-obligor/seniority netting, HBR, bucket
  capital, category aggregation, and total DRC all run through one public API;
- results are frozen, serialisable, and carry rule-profile/input hashes;
- securitisation non-CTP and CTP requests fail explicitly;
- tests cover long-only, short-only, offsetting, maturity under one year,
  maturity under three months, seniority rejection, defaulted exposures, LGD
  categories, bucket floors, missing risk weights, and audit hash stability.
