# frtb-cva detailed requirements

## Purpose

`frtb-cva` must implement CVA risk capital as an auditable capital component in the
`frtb-capital` suite. It consumes canonical counterparty, netting-set exposure,
hedge, and SA-CVA sensitivity records from upstream risk systems or adapters,
calculates BA-CVA and/or SA-CVA capital under a selected rule profile, and emits
frozen result records for orchestration.

The package is a capital layer only. It does not simulate counterparty exposure
paths, source market data, produce accounting CVA, price trades, maintain
counterparty master data, or prepare regulatory submissions. Upstream systems
remain responsible for regulatory CVA modelling, exposure-at-default (EAD)
calculation, and CVA sensitivity generation where SA-CVA is used.

CVA is architecturally distinct from the Standardised Approach stack
(`frtb-sbm + frtb-drc + frtb-rrao`). See
[ADR 0003](../../decisions/0003-sa-drc-cva-scope.md).

## Source hierarchy

Implementation must treat regulatory source text as authoritative and repository
planning documents as suite-specific build guidance.

| Priority | Source | Use |
| --- | --- | --- |
| 1 | [Basel MAR50](https://www.bis.org/basel_framework/chapter/MAR/50.htm) | CVA definitions, scope, BA-CVA, SA-CVA, eligible hedges, aggregation, multiplier, and risk-class tables. |
| 1 | [U.S. NPR 2.0, 91 FR 14952](https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959) | Proposed U.S. CVA risk scope, CVA hedges, internal CVA risk transfers, and CVA measures, section V.B. |
| 2 | [CRR3 Regulation (EU) 2024/1623](https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng) | EU comparison profile, CRR Articles 382–386 and related CVA provisions. |
| 2 | [EBA RTS on CVA risk of SFTs](https://www.eba.europa.eu/activities/single-rulebook/regulatory-activities/market-counterparty-and-cva-risk/regulatory-technical-standards-cva-risk-securities-financing-transactions) | EU technical context for SFT CVA scope. |
| 3 | Current repository CVA PRD and regulatory requirements | Product scope, architecture intent, delivery slices, package boundary within this suite. |
| 3 | Existing IMA, DRC, RRAO, and SBM detailed requirements | Quality bar, traceability standard, fail-closed behaviour, audit/readiness expectations. |
| 4 | External/local reference implementation | Naming and decomposition inspiration only; never a substitute for citations. |

Every rule-driven quantity must have a paragraph, article, proposed section, or
table citation. Do not cite only "Basel" or "U.S. NPR" when documenting a formula
or lookup.

Note on calibration revisions: the Basel Committee's July 2020 targeted revisions
([BCBS d507](https://www.bis.org/bcbs/publ/d507.pdf)) reduced `m_CVA` from 1.25
to 1.0 for SA-CVA and introduced the BA-CVA discount scalar
`D_BA-CVA = 0.65`. Profile implementations must cite the publication date and
paragraph version they implement; mixed calibration without explicit profile
metadata is not permitted.

## Product boundary requirements

### CVA-BOUNDARY-001: Package responsibility

`frtb-cva` owns CVA risk capital for:

- BA-CVA reduced version (no hedge recognition);
- BA-CVA full version (counterparty credit spread hedge recognition with
  supervisory floor);
- SA-CVA delta and vega capital across the six prescribed delta risk classes
  and five prescribed vega risk classes;
- eligible CVA hedge recognition and CVA/hedge sensitivity netting where cited;
- method selection, carve-out, and materiality-threshold policy hooks;
- portfolio-level CVA capital aggregation and multiplier application.

It must expose package-level CVA outputs only. `frtb-orchestration` owns
top-of-house aggregation across IMA, SA components, CVA, and any firm-level
floors or redesignation add-ons.

### CVA-BOUNDARY-002: No sibling package imports

`frtb-cva` may import from `frtb-common`. It must not import from `frtb-ima`,
`frtb-sbm`, `frtb-drc`, or `frtb-rrao`.

SA-CVA reuses SBM-style delta/vega aggregation mechanics in regulatory text, but
the implementation must remain package-local. Shared abstractions that genuinely
belong in `frtb-common` require a cross-cutting ADR before extraction.

### CVA-BOUNDARY-003: Upstream inputs, not exposure simulation

The capital package receives:

- counterparty and netting-set identity;
- EAD or profile-equivalent exposure measure;
- effective maturity and discount-factor inputs where required by BA-CVA;
- pre-computed CVA and hedge sensitivities for SA-CVA;
- hedge eligibility evidence and internal/external transfer flags.

It must not simulate discounted exposure paths, calibrate exposure models, or
generate CVA sensitivities from trade economics. Regulatory CVA modelling
principles in Basel MAR50.31–MAR50.36 and U.S. NPR 2.0 section V.B govern
upstream systems; this package validates that supplied inputs are sufficient for
the selected method and applies cited capital mechanics.

### CVA-BOUNDARY-004: Fail-closed unsupported scope

Any requested path without cited rule mapping and deterministic test evidence
must raise an explicit `UnsupportedRegulatoryFeatureError` or package-specific
input error. The package must not emit zero, empty, or placeholder capital for
unsupported methods, risk classes, hedge types, profile features, or partial
BA-CVA/SA-CVA combinations.

### CVA-BOUNDARY-005: Profile-driven behaviour

Risk weights, bucket definitions, correlation parameters, hedge eligibility
rules, maturity/discount policies, multipliers, scalars, scenario labels, and
citation metadata must come from a versioned rule profile, not global constants
embedded in kernels.

### CVA-BOUNDARY-006: Hedge benefit is never implicit

CVA hedge capital benefit must be applied only when hedge eligibility is
explicitly recorded with evidence, citation ids, and method-specific checks.
Ineligible hedges must be rejected or capitalised elsewhere according to profile
rules, never silently ignored or treated as zero.

### CVA-BOUNDARY-007: Canonical-first calculation

Calculation kernels must operate on canonical typed records. CRIF/CSV/vendor
formats may be supported through adapters, but adapters are not part of the
kernel and must preserve lineage and mapping evidence.

## Functional requirements

### CVA-FUNC-001: Public calculation entry point

The public API must accept:

- canonical `CvaCounterparty`, `CvaNettingSet`, `CvaHedge`, and/or
  `SaCvaSensitivity` records as required by the selected method;
- a `CvaCalculationContext` containing run identity, scope, calculation date,
  base/reporting currency, selected CVA method, selected rule profile, and
  citation policy;
- optional run controls for audit verbosity, unsupported-feature behaviour, and
  intermediate-detail retention.

The public API must return a frozen `CvaCapitalResult` only when all requested
features are supported and input validation passes.

Basel anchor: MAR50.6–MAR50.7. U.S. anchor: NPR 2.0 section V.B.2–V.B.3.

### CVA-FUNC-002: Canonical counterparty input model

Each counterparty record must carry, at minimum:

- stable `counterparty_id` and `source_row_id`;
- `legal_entity`, `desk_id`, and optional portfolio scope fields;
- sector and credit-quality classification inputs required by the active profile;
- `region` required for BA-CVA indirect hedge eligibility (Basel MAR50.19(3) and
  Table 2 in MAR50.26);
- covered-transaction eligibility flags and exclusion reasons where supplied;
- internal-rating-to-external-rating mapping evidence where the profile permits
  IG/HY mapping for unrated names (Basel MAR50.16 footnote);
- source lineage and citation-support metadata for every mapped regulatory field.

### CVA-FUNC-003: Canonical netting-set exposure input model

Each netting-set record must carry, at minimum:

- stable `netting_set_id`, `counterparty_id`, and `source_row_id`;
- `ead` or profile-equivalent exposure measure, non-negative and finite;
- `effective_maturity` (`M_NS`) under the profile's cited definition;
- `discount_factor` (`DF_NS`) where required for non-IMM banks (Basel MAR50.15(4)),
  either supplied explicitly or computed by the profile helper as
  `DF = (1 - exp(-0.05 · M)) / (0.05 · M)`;
- `uses_imm_ead` flag driving the IMM branch where `DF_NS = 1` (Basel MAR50.15(4));
- collateral and margin metadata references where supplied for audit, without
  re-simulating margin paths in the kernel;
- currency and sign convention;
- carve-out / synthetic split flags where SA-CVA approval is partial (Basel
  MAR50.8);
- source lineage and citation ids.

Basel anchors: MAR50.8, MAR50.12, MAR50.15. U.S. anchor: NPR 2.0 section V.B.3.

### CVA-FUNC-004: Canonical hedge input model

Each hedge record must carry, at minimum:

- stable `hedge_id`, `source_row_id`, and hedge-to-counterparty or index mapping;
- `hedge_type` and instrument descriptors required by the active method;
- reference-entity sector and `region` where indirect hedge eligibility applies
  (Basel MAR50.19(3), MAR50.26);
- `notional`, `remaining_maturity`, and discount-factor inputs for BA-CVA full
  version (Basel MAR50.23–MAR50.25);
- internal vs external flag and internal-desk counterparty reference for transfer
  treatment (Basel MAR50.11);
- eligibility evidence: purpose, management desk, whole-transaction flag, and
  rejected-eligibility reason when ineligible;
- SA-CVA risk-class assignment for credit-spread hedges (counterparty credit
  spread vs reference credit spread, entire instrument, no split — Basel
  MAR50.44);
- source lineage and citation ids.

### CVA-FUNC-005: Canonical SA-CVA sensitivity input model

Each SA-CVA sensitivity record must represent one **portfolio-level** CVA or
hedge sensitivity contribution before weighting and aggregation. Sensitivities
are defined on the aggregate CVA portfolio and eligible hedges per Basel
MAR50.47, not at counterparty level. Multiple rows sharing the same portfolio
risk-factor key must be summed deterministically before weighting (see
[CVA-DEC-004](DECISIONS_AND_PLAN.md#cva-dec-004-sa-cva-sensitivities-are-portfolio-aggregate-inputs)
and [ARCHITECTURE_AND_DATA_DESIGN.md](ARCHITECTURE_AND_DATA_DESIGN.md)). A record
must carry, at minimum:

- stable `sensitivity_id` and `source_row_id`;
- `risk_class`: GIRR, FX, counterparty credit spread (CCS), reference credit
  spread (RCS), equity, or commodity;
- `risk_measure`: delta or vega;
- `sensitivity_tag`: `CVA`, `HDG`, or derived `NET` after permitted netting;
- bucket, `risk_factor_key`, optional tenor, qualifier, and index-bucket option
  flags where required by the active risk class;
- raw sensitivity amount, amount currency, and sign convention consistent with
  positive-loss regulatory CVA convention (Basel MAR50.32(1), MAR50.52 footnote);
- `volatility_input` (`σ_k`) where the active profile prescribes vega weights
  of the form `RW_k = RW_σ · σ_k` (Basel MAR50.58 and analogous vega paragraphs);
- source lineage and citation ids.

Public boundaries may accept raw strings, but calculation kernels must receive
normalised enums and finite numeric values.

Basel anchors: MAR50.47–MAR50.51. U.S. anchor: NPR 2.0 section V.B.6.

### CVA-FUNC-006: Scope, exclusions, and method selection

The policy layer must support explicit classification of:

- covered transactions under Basel MAR50.5(1)–(2): non-centrally-cleared
  derivatives except QCCP and CRE54.14–CRE54.16 cases; material fair-valued SFTs;
- regulatory vs accounting CVA distinction (Basel MAR50.2–MAR50.4);
- default method rule: BA-CVA unless SA-CVA is approved (Basel MAR50.7);
- SA-CVA carve-out of netting sets to BA-CVA, including synthetic split rules
  (Basel MAR50.8);
- materiality-threshold alternative: aggregate non-centrally-cleared notional
  ≤ EUR 100bn with 100% of CCR capital alternative and no hedge recognition
  (Basel MAR50.9);
- unsupported or supervisor-removed alternatives failing closed.

The selected method, carve-outs, and exclusions must appear in the result record
with citation ids.

### CVA-FUNC-007: Internal CVA hedge and transfer treatment

The package must implement Basel MAR50.11 internal/external hedge routing at
the capital layer:

- eligible external hedges excluded from market-risk capital and included in
  CVA portfolio calculations;
- ineligible external hedges capitalised under market-risk rules outside this
  package;
- eligible internal hedges: CVA-desk leg in CVA portfolio, trading-desk leg in
  market-risk capital outside this package;
- ineligible internal hedges: both legs remain in trading book with no CVA
  benefit;
- curvature/default/RRAO-affected internal hedges eligible only with exact
  external back-to-back offset (Basel MAR50.11(5)).

U.S. comparison hooks: NPR 2.0 section V.A.6.c and section V.B.3 for CVA segment
and trading-desk segment treatment.

The package records eligibility decisions and branch metadata; it does not
execute desk governance workflows.

### CVA-FUNC-008: BA-CVA reduced version

The reduced BA-CVA path must calculate `K_reduced` per Basel MAR50.14:

- stand-alone counterparty capital `SCVA_c` per netting set using supervisory
  multiplier `α = 1.4`, `RW_c`, `M_NS`, `EAD_NS`, and `DF_NS` (Basel MAR50.15);
- supervisory correlation `ρ = 50%`;
- portfolio aggregation of systematic and idiosyncratic components across
  counterparties;
- application of discount scalar `D_BA-CVA = 0.65` to produce final reduced
  capital.

The result must preserve, per counterparty and netting set:

- sector/credit-quality bucket and selected `RW_c` from Table 1 (Basel MAR50.16);
- unscaled and final stand-alone capital;
- EAD, maturity, discount factor, and α inputs;
- citation ids and source lineage.

Exposure hedges are not recognised in reduced BA-CVA (Basel MAR50.13(2)).

### CVA-FUNC-009: BA-CVA supervisory risk weights

The first Basel profile must implement Table 1 sector/credit-quality risk weights
from Basel MAR50.16, including at minimum:

- sovereign IG 0.5%, HY/NR 2.0% (post-2020 revision for HY/NR sovereigns);
- local government / government-backed non-financials IG 1.0%, HY/NR 4.0%;
- financials IG 5.0%, HY/NR 12.0%;
- basic materials / energy / industrials IG 3.0%, HY/NR 7.0%;
- consumer / transport / admin IG 3.0%, HY/NR 8.5%;
- technology / telecom IG 2.0%, HY/NR 5.5%;
- health / utilities / professional IG 1.5%, HY/NR 5.0%;
- other sector IG 5.0%, HY/NR 12.0%.

Missing sector/credit-quality keys must raise input errors unless the profile
explicitly marks the combination unsupported.

### CVA-FUNC-010: BA-CVA full version and hedge recognition

The full BA-CVA path must:

- always compute reduced BA-CVA `K_reduced` (Basel MAR50.20);
- compute hedged capital `K_hedged` using single-name hedge recognition `SNH_c`,
  index hedge recognition `IH`, and hedging misalignment `HMA_c` (Basel
  MAR50.21–MAR50.25);
- apply supervisory floor
  `K_full = β · K_reduced + (1 - β) · K_hedged` with `β = 0.25` (Basel MAR50.20);
- apply discount scalar `D_BA-CVA = 0.65`.

Eligible BA-CVA hedge instruments are limited to single-name CDS, single-name
contingent CDS, and index CDS (Basel MAR50.18). Reference-name eligibility follows
Basel MAR50.19 and correlation table MAR50.26:

- direct counterparty reference: `r_hc = 100%`;
- legal relation: `r_hc = 80%`;
- same sector and region: `r_hc = 50%`.

Index hedge risk weights use Table 1 with 0.7 diversification scalar (Basel
MAR50.24(4)).

The audit trail must retain gross hedge notionals, discount factors, misalignment
terms, floor binding status, and rejected hedge records with reason codes.

### CVA-FUNC-011: SA-CVA eligibility and input sufficiency gates

Before SA-CVA capital is calculated, the profile/policy layer must verify the
run declares SA-CVA approval and supplies the sensitivity set required by the
requested risk classes. Upstream governance criteria in Basel MAR50.30 (monthly
CVA and sensitivity modelling capability; dedicated CVA desk) are recorded as
policy metadata, not re-validated by the kernel beyond explicit context flags.

If SA-CVA is requested without required sensitivities for a supported risk
class, the package must fail closed rather than treat missing sensitivities as
zero capital.

### CVA-FUNC-012: SA-CVA sensitivity validation and CVA/hedge tagging

For SA-CVA, the package must:

- accept separate CVA (`s_k^CVA`) and hedge (`s_k^Hdg`) sensitivities per risk
  factor (Basel MAR50.47);
- compute weighted sensitivities `WS_k^CVA = s_k^CVA · RW_k` and
  `WS_k^Hdg = s_k^Hdg · RW_k` (Basel MAR50.51);
- compute net weighted sensitivity
  `WS_k = WS_k^CVA − WS_k^Hdg` under the positive regulatory CVA sign convention
  (Basel MAR50.52 and footnote);
- preserve gross CVA, gross hedge, and net values in audit records;
- apply hedging disallowance parameter `R = 0.01` at bucket level (Basel
  MAR50.53(1)).

Only eligible hedge sensitivities may be included in `s_k^Hdg`. Ineligible hedge
rows must be rejected at validation or recorded as excluded with zero hedge
contribution explicitly.

### CVA-FUNC-013: SA-CVA shared aggregation engine

The SA-CVA engine must implement the cited three-level aggregation common to all
risk classes and measures:

1. **Intra-bucket risk-factor aggregation** to bucket capital `K_b` using
   intra-bucket correlations `ρ_kl` and hedging disallowance term (Basel
   MAR50.53(1)).
2. **Inter-bucket aggregation** to risk-class capital `K` using cross-bucket
   correlations `γ_bc`, bucket sums `S_b` floored/capped by `±K_b` (Basel
   MAR50.53(2)–(3)).
3. **Multiplier application** `K = m_CVA · sqrt(...)` at the risk-class level
   (Basel MAR50.53(2)).

Delta and vega capital for each risk class use the same procedures (Basel
MAR50.46). Total SA-CVA capital is the simple sum of delta and vega capital
across all risk classes (Basel MAR50.42–MAR50.43, MAR50.45).

The engine must preserve pairwise correlation evidence, bucket inputs, scenario
labels where applicable, and branch metadata for floors and caps.

### CVA-FUNC-014: SA-CVA multiplier

The profile must expose `m_CVA` with cited default and supervisor-override
behaviour (Basel MAR50.40–MAR50.41). The first Basel profile should default to
1.0 per the July 2020 revision unless a profile explicitly documents an earlier
1.25 calibration with publication metadata.

Results must expose pre-multiplier and post-multiplier risk-class and total
capital.

### CVA-FUNC-015: SA-CVA GIRR requirements

The GIRR path must support Basel MAR50.54–MAR50.58:

- buckets per currency; cross-bucket `γ_bc = 0.5`;
- specified-currency delta factors: 1y, 2y, 5y, 10y, 30y yields plus inflation;
  cited delta risk weights and `ρ_kl` table;
- other-currency delta: parallel curve shift plus inflation, cited weights and
  correlations;
- vega: simultaneous relative shift of interest-rate and inflation volatilities;
  `RW_k = RW_σ · σ_k` with cited `RW_σ`, where `σ_k` is supplied on sensitivity
  inputs or via explicit profile-permitted defaults.

### CVA-FUNC-016: SA-CVA FX requirements

The FX path must support Basel MAR50.59–MAR50.62:

- buckets per currency except reporting currency; cross-bucket `γ_bc = 0.6`;
- delta: 1% relative shift in FX spot vs reporting currency; cited delta risk
  weight 21%;
- non-reporting currency pair transactions require sensitivity to reporting
  currency against each leg (Basel MAR50.61 footnote);
- vega: simultaneous 1% relative shift in FX volatilities; cited vega weight
  formula.

### CVA-FUNC-017: SA-CVA counterparty credit spread (CCS) requirements

The CCS path must support Basel MAR50.63–MAR50.65:

- delta only; no vega capital for counterparty credit spread risk (Basel
  MAR50.45, MAR50.63);
- buckets 1–7 by sector plus optional bucket 8 qualified indices (Basel
  MAR50.50, MAR50.63);
- delta risk factors: 0.5y, 1y, 3y, 5y, 10y absolute spread shifts;
- cited bucket risk weights for IG and HY/NR names;
- cited `ρ_kl` structure for same/different name, tenor, credit quality, and
  legal relation;
- cited cross-bucket `γ_bc` table.

Index look-through vs qualified-index bucket treatment must follow MAR50.50 and
MAR50.63(2) explicitly; mixed treatment without evidence must fail closed.

### CVA-FUNC-018: SA-CVA reference credit spread (RCS) requirements

The RCS path must support Basel MAR50.66–MAR50.69:

- delta and vega buckets 1–17 including qualified-index buckets;
- simultaneous bucket-wide spread shift for delta; simultaneous relative
  volatility shift for vega;
- cited IG/HY/NR bucket risk weights;
- cited cross-bucket `γ_bc` table, including divide-by-2 rule for IG vs HY/NR
  cross-quality pairs (Basel MAR50.67(2)).

### CVA-FUNC-019: SA-CVA equity requirements

The equity path must support Basel MAR50.70–MAR50.73:

- bucket structure by size, region, sector, and qualified indices;
- market-cap and advanced-economy definitions as profile metadata;
- cited delta risk weights by bucket;
- vega risk weights using cited `RW_σ` scalars by size bucket;
- cross-bucket `γ_bc`: 15% within buckets 1–10, 75% between buckets 12 and 13,
  45% between 12/13 and 1–10, 0% when bucket 11 involved.

### CVA-FUNC-020: SA-CVA commodity requirements

The commodity path must support Basel MAR50.74–MAR50.77:

- eleven commodity-group buckets plus other commodity bucket;
- cross-bucket `γ_bc = 20%` within buckets 1–10, 0% when bucket 11 involved;
- simultaneous 1% relative shift in bucket spot prices for delta;
- simultaneous 1% relative shift in bucket volatilities for vega;
- cited delta and vega risk weights by bucket.

### CVA-FUNC-021: Qualified index option

Where the active profile supports the MAR50.50 index-bucket option for CCS, RCS,
and equity, the package must:

- accept qualified-index risk factors in addition to constituent factors;
- replace constituent contributions with a single index sensitivity when criteria
  are met;
- enforce look-through when index buckets 1–7 (CCS) or non-qualified indices are
  used;
- enforce sector concentration rule: >75% constituents in one sector maps index
  to single-name bucket (Basel MAR50.50(6)).

Unsupported index treatments must fail closed until fixtures and profile tables
are complete.

### CVA-FUNC-022: Method combination and carve-out assembly

When a run includes both SA-CVA and BA-CVA components (netting-set carve-outs),
the result must:

- calculate SA-CVA on in-scope sensitivities and BA-CVA on carved-out
  counterparties/netting sets separately;
- sum component totals only where the profile permits;
- preserve component lineage and disallow double-counting of hedges across methods;
- fail closed if carve-out evidence is incomplete.

Basel anchor: MAR50.8.

### CVA-FUNC-023: Public result model

The result model must include, at minimum:

- total CVA capital and selected method (`BA-CVA reduced`, `BA-CVA full`,
  `SA-CVA`, materiality alternative, or mixed with carve-out);
- BA-CVA counterparty/netting-set line records where applicable;
- SA-CVA risk-class delta/vega totals pre- and post-multiplier;
- bucket-level capital records and weighted sensitivity records or equivalent
  explain surface;
- hedge recognition summary: eligible, ineligible, excluded from SA-CVA, floor
  bound in BA-CVA full version;
- rule profile id and hash;
- input snapshot hash;
- supported/unsupported feature flags;
- warnings and reconciliation metadata;
- requirement ids and citation ids.

Basel MAR50.1: RWA equals capital times 12.5. The package may expose RWA as a
derived field but must treat CVA capital as the primary audit quantity.

### CVA-FUNC-024: Audit and replay

Every successful capital result must carry enough metadata to reproduce the
number deterministically, including:

- package name and version;
- run id and calculation date;
- base/reporting currency;
- selected CVA method and carve-out flags;
- rule profile id, publication date, and profile hash;
- input snapshot hash;
- deterministic input counts and rejected-input counts by record type;
- requirement ids and citation ids;
- stable ids for counterparty, netting set, hedge, sensitivity, bucket,
  risk-class, and total records.

Audit serialisation must be deterministic and JSON/Markdown ready.

U.S. comparison anchor: NPR 2.0 section V.B.6 for measure reporting expectations.

### CVA-FUNC-025: Explain and contribution readiness

The package must preserve stable ids, deterministic ordering, intermediate
aggregation records, and branch metadata so later analytical Euler contribution
or impact analysis can be added without changing the public capital API.

The first capital slices do not need full Euler allocation, but they must not
block it structurally. See
[ADR 0012](../../decisions/0012-capital-impact-attribution.md).

SA-CVA aggregation nonlinearities (square roots, floors/caps on `S_b`, hedge
disallowance term) require explicit branch metadata for any future attribution
slice.

### CVA-FUNC-026: Adapter boundary

The package may provide CRIF/vendor-to-canonical mapping, but:

- adapters must not be required by the capital kernel;
- adapter output must be canonical package records;
- source column names, row ids, mapping warnings, and inferred-field decisions
  must be preserved;
- adapters may use Arrow at the handoff boundary under ADR 0023, but must not
  introduce dataframe execution or Arrow objects into the kernel path.

External reference implementations may inform column naming; they are not
regulatory sources.

### CVA-FUNC-027: Explicit unsupported-feature reporting

Unsupported paths must identify the failing dimension explicitly, for example:

- unsupported profile or method;
- unsupported risk class or risk measure;
- missing bucket mapping or risk weight;
- missing EAD, maturity, or discount factor for BA-CVA;
- ineligible hedge type or split-instrument attempt;
- missing CVA or hedge sensitivity for requested SA-CVA risk class;
- unsupported qualified-index treatment;
- unimplemented materiality-threshold alternative;
- mixed calibration profile without explicit publication metadata.

## Non-functional requirements

### CVA-NFR-001: Determinism

Outputs must be deterministic for the same ordered canonical inputs, rule
profile, and code version. Grouping and serialisation must use stable keys, not
incidental dictionary ordering. Determinism checks must use raw numeric hashes
rather than rounding floating-point outputs, and must document platform or BLAS
limits where relevant.

### CVA-NFR-002: Runtime dependency policy

Core runtime kernels must use Python standard library, frozen dataclasses,
enums, and package-owned `numpy` arrays where vectorisation matters. Arrow may
be used only for tabular handoff, CRIF normalization, adapters, and handoff
objects under
[ADR 0023](../../decisions/0023-arrow-tabular-handoff-boundary.md). Kernels
must not import `pyarrow`, `pandas`, or `polars`. Additional runtime numerical
dependencies beyond the approved Arrow handoff boundary require explicit design
approval consistent with
[ADR 0011](../../decisions/0011-core-runtime-dependency-policy.md).

### CVA-NFR-003: Numeric representation

Aggregation paths should use `float64` arrays where performance matters while
preserving original input amounts in audit records. Tests must explicitly cover
sign, zero, floor/cap, near-zero, and hedge-disallowance behaviour.

### CVA-NFR-004: Validation

Validation must reject:

- missing identity fields;
- unknown enum values;
- duplicate stable ids unless an adapter explicitly aggregates rows;
- non-finite numeric amounts;
- negative EAD where non-negative exposure is required;
- missing source row ids;
- implicit sign conventions;
- `region` on counterparty and hedge reference metadata where BA-CVA indirect
  hedge eligibility applies;
- ineligible hedge rows presented as eligible without evidence;
- credit-spread hedge assigned to both CCS and RCS;
- missing citation ids for rule-driven profile data;
- unsupported method/profile/risk-class combinations.

### CVA-NFR-005: Test evidence

Every implemented calculation feature must have:

- deterministic unit tests;
- invalid-input tests;
- unsupported-feature tests;
- cited fixture or hand-worked reference-vector tests;
- audit metadata and replay/hash tests;
- reconciliation tests from sensitivity through bucket, risk class, and total.

### CVA-NFR-006: Synthetic-data-only evidence

Validation fixtures, examples, and tests must use synthetic data only.

### CVA-NFR-007: Performance target

The first production-quality SA-CVA aggregation slice should include a benchmark
target sufficient to show the package remains usable for large synthetic
sensitivity sets. This is an engineering control, not a regulatory requirement.

The first BA-CVA slice should benchmark at least 10,000 netting sets across 1,000
counterparties with mixed sectors and credit qualities.

### CVA-NFR-008: Regulatory caution

No document, API, or output should present results as final regulatory capital.
Outputs remain model/engineering artifacts unless independently validated and
approved.

## Initial implementation acceptance criteria

The first capital-producing vertical slice is complete only when:

- canonical counterparty and netting-set records validate and normalise;
- reduced BA-CVA runs through one public API using cited Table 1 risk weights,
  MAR50.14–MAR50.15 mechanics, and `D_BA-CVA = 0.65`;
- EAD, maturity, and discount-factor inputs are validated and traceable;
- results are frozen, serialisable, and carry rule-profile and input hashes;
- SA-CVA, full BA-CVA, carve-out mixed runs, and materiality-threshold
  alternative requests fail explicitly;
- tests cover at least one sovereign IG, one financial HY, multi-netting-set
  counterparty, invalid EAD, missing risk weight, missing maturity, and audit-hash
  stability.

The second vertical slice adds SA-CVA common aggregation plus one risk class
(GIRR delta is the recommended first SA-CVA class because of simpler bucket
structure and broad fixture reuse patterns from SBM documentation).

## Recommended delivery slicing constraints

The [ISSUE_BREAKDOWN.md](ISSUE_BREAKDOWN.md) sequence governs v1 implementation
order and supersedes PRD delivery-slice ordering where they differ (for example,
hedge eligibility after the first reduced BA-CVA capital slice). See
[CVA-DEC-011](DECISIONS_AND_PLAN.md#cva-dec-011-issue-sequence-supersedes-prd-delivery-slice-ordering).

To stay aligned with repository style, issue breakdown should follow these
constraints:

1. Skeleton, traceability, and requirements registry alignment first.
2. Canonical data models and validation before any capital math.
3. Rule-profile and reference-data layer before method-specific kernels.
4. BA-CVA reduced version as the first capital-producing slice.
5. Shared SA-CVA weighting/aggregation engine before multiple SA-CVA risk classes.
6. One thin SA-CVA end-to-end path early (GIRR delta recommended).
7. BA-CVA full version after reduced BA-CVA and hedge contracts are stable.
8. Remaining SA-CVA risk classes incrementally (FX, CCS, RCS, equity, commodity;
   vega after delta per class where applicable).
9. Qualified-index option and carve-out mixed-method assembly after base paths.
10. Audit/replay and benchmark reports before orchestration integration.
11. Adapters after canonical runtime exists.

## Related planning documents

- [ARCHITECTURE_AND_DATA_DESIGN.md](ARCHITECTURE_AND_DATA_DESIGN.md) — module
  layout, input granularity, enums, dataclasses, reconciliation rules.
- [DECISIONS_AND_PLAN.md](DECISIONS_AND_PLAN.md) — profile locality, sign
  convention, portfolio-level SA-CVA inputs, implementation sequence.
- [ISSUE_BREAKDOWN.md](ISSUE_BREAKDOWN.md) — PR-sized implementation issues.

## Gaps this document closes vs the current CVA docs

The current CVA PRD and regulatory requirements define scope and architecture
intent but lacked the issue-ready detail present in DRC, RRAO, and SBM. This
document adds:

- explicit package boundary and upstream/downstream split for exposure and
  sensitivity generation;
- canonical input and public result requirements by record type;
- method-selection, carve-out, and materiality-threshold requirements;
- BA-CVA reduced and full formulas with hedge-floor mechanics;
- SA-CVA tagging, netting, hedging-disallowance, and three-level aggregation;
- risk-class-specific functional requirements grounded in MAR50.54–MAR50.77;
- qualified-index option requirements;
- fail-closed unsupported behaviour;
- audit, replay, and attribution-readiness requirements;
- non-functional and validation requirements;
- issue-friendly requirement IDs and first-slice acceptance criteria.

## Requirement ID index

| ID | Title |
| --- | --- |
| CVA-BOUNDARY-001 | Package responsibility |
| CVA-BOUNDARY-002 | No sibling package imports |
| CVA-BOUNDARY-003 | Upstream inputs, not exposure simulation |
| CVA-BOUNDARY-004 | Fail-closed unsupported scope |
| CVA-BOUNDARY-005 | Profile-driven behaviour |
| CVA-BOUNDARY-006 | Hedge benefit is never implicit |
| CVA-BOUNDARY-007 | Canonical-first calculation |
| CVA-FUNC-001 | Public calculation entry point |
| CVA-FUNC-002 | Canonical counterparty input model |
| CVA-FUNC-003 | Canonical netting-set exposure input model |
| CVA-FUNC-004 | Canonical hedge input model |
| CVA-FUNC-005 | Canonical SA-CVA sensitivity input model |
| CVA-FUNC-006 | Scope, exclusions, and method selection |
| CVA-FUNC-007 | Internal CVA hedge and transfer treatment |
| CVA-FUNC-008 | BA-CVA reduced version |
| CVA-FUNC-009 | BA-CVA supervisory risk weights |
| CVA-FUNC-010 | BA-CVA full version and hedge recognition |
| CVA-FUNC-011 | SA-CVA eligibility and input sufficiency gates |
| CVA-FUNC-012 | SA-CVA sensitivity validation and CVA/hedge tagging |
| CVA-FUNC-013 | SA-CVA shared aggregation engine |
| CVA-FUNC-014 | SA-CVA multiplier |
| CVA-FUNC-015 | SA-CVA GIRR requirements |
| CVA-FUNC-016 | SA-CVA FX requirements |
| CVA-FUNC-017 | SA-CVA CCS requirements |
| CVA-FUNC-018 | SA-CVA RCS requirements |
| CVA-FUNC-019 | SA-CVA equity requirements |
| CVA-FUNC-020 | SA-CVA commodity requirements |
| CVA-FUNC-021 | Qualified index option |
| CVA-FUNC-022 | Method combination and carve-out assembly |
| CVA-FUNC-023 | Public result model |
| CVA-FUNC-024 | Audit and replay |
| CVA-FUNC-025 | Explain and contribution readiness |
| CVA-FUNC-026 | Adapter boundary |
| CVA-FUNC-027 | Explicit unsupported-feature reporting |
| CVA-NFR-001 | Determinism |
| CVA-NFR-002 | Runtime dependency policy |
| CVA-NFR-003 | Numeric representation |
| CVA-NFR-004 | Validation |
| CVA-NFR-005 | Test evidence |
| CVA-NFR-006 | Synthetic-data-only evidence |
| CVA-NFR-007 | Performance target |
| CVA-NFR-008 | Regulatory caution |
