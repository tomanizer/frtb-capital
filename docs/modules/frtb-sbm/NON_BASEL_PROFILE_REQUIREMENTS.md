# SBM non-Basel profile — detailed requirements

Normative requirements for expanding `frtb-sbm` beyond `BASEL_MAR21`. Design
context: [NON_BASEL_PROFILE_DESIGN.md](NON_BASEL_PROFILE_DESIGN.md).

Requirement ids use prefix **SBM-NBP-** (non-Basel profile). They supplement,
not replace, [DETAILED_REQUIREMENTS.md](DETAILED_REQUIREMENTS.md) (`SBM-FUNC-*`,
`SBM-BOUNDARY-*`).

## Source hierarchy (non-Basel)

| Priority | Source | Profile |
| --- | --- | --- |
| 1 | [91 FR 14952](https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959), section V.A.7.a | `US_NPR_2_0` |
| 1 | [Regulation (EU) 2024/1623](https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng), Arts. 325e–325az | `EU_CRR3` |
| 1 | [PRA PS1/26 Appendix 1](https://www.bankofengland.co.uk/-/media/boe/files/prudential-regulation/policy-statement/2026/january/ps126app1.pdf), Market Risk: Advanced Standardised Approach (CRR) Part, Arts. 325c-325ay | `PRA_UK_CRR` |
| 3 | [NON_BASEL_PROFILE_DESIGN.md](NON_BASEL_PROFILE_DESIGN.md) | Sequencing and matrix |

Proposed U.S. rule text is comparison material only. Every implemented
threshold must cite a specific section, table, or article — not “U.S. NPR 2.0”
alone.

---

## Matrix and traceability requirements

### SBM-NBP-001: Authoritative support matrix

The package must maintain a **profile × risk-class × risk-measure** matrix
covering all four `SbmRegulatoryProfile` values and seven `SbmRiskClass` × three
`SbmRiskMeasure` combinations (84 cells total).

The matrix must assign exactly one status per cell from:

- implemented under audit;
- unsupported fail-closed;
- planned;
- blocked;
- out of scope.

**Documentation location:** `packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md`
(non-Basel section expanded to per-class rows).  
**Design summary:** [NON_BASEL_PROFILE_DESIGN.md](NON_BASEL_PROFILE_DESIGN.md).

### SBM-NBP-002: Code–documentation parity

`phase1_capital_supported_paths(profile_id)` in `validation/context.py` must
match the matrix for every cell marked implemented. Tests in
`tests/test_sbm_support_matrix.py` must fail if parity breaks.

### SBM-NBP-003: Source manifest linkage

Each profile family used for implementation must have an entry in
`packages/frtb-sbm/docs/regulatory_sources.yml` with `section_hint` granular
enough for reviewers to locate bucket/weight tables. `PRA_UK_CRR` is now
source-mapped to PRA PS1/26 Appendix 1 / PRA2026/1, but the mapped source is not
authority for capital-producing runtime until exact-cell citation ids,
profile-owned reference data, and deterministic fixtures are added.

### SBM-NBP-004: Basel sub-feature matrix

Basel-only unsupported sub-features (e.g. equity `REPO` vega/curvature) must be
listed separately from profile-level gaps so audit readers do not interpret them
as NPR/EU/PRA backlog.

---

## Profile boundary requirements

### SBM-NBP-010: No silent Basel fallback

When `profile_id` is `US_NPR_2_0`, `EU_CRR3`, or `PRA_UK_CRR`, the package must
not read `PROFILE_*[BASEL_MAR21]` tables, must not coerce profile to Basel, and
must not return capital labelled with Basel citation ids.

Violation: automatic fail of review and QC.

### SBM-NBP-011: Incremental profile enablement

Enabling a comparison profile must occur **per risk-class/measure cell** by
updating:

1. `_PHASE1_SUPPORTED[profile_id]`;
2. `PROFILE_SUPPORTED_MEASURES`;
3. `SUPPORTED_PROFILE_METADATA` / removal from `UNSUPPORTED_PROFILE_REASONS` when
   the profile has at least one supported cell;
4. `PROFILE_*` reference-data maps for that cell;
5. `REGULATORY_TRACEABILITY.md`;
6. tests and fixtures.

Partial profiles (some cells implemented, others fail-closed) are required
during rollout.

### SBM-NBP-012: Unknown profile input

Unknown `profile_id` strings must continue to raise `SbmInputError` with an
enumerated allowed list (`ensure_sbm_profile_known`).

### SBM-NBP-013: Blocked profile behaviour

`PRA_UK_CRR` must remain unsupported fail-closed at runtime until the exact
profile/risk-class/measure cell has profile-owned citations, reference data, and
fixtures. `PRA_UK_CRR` GIRR delta satisfies that standard and is implemented
under audit; the remaining 20 PRA cells must remain fail-closed until their own
cell-specific evidence lands. Documentation must mark each cell according to
that exact-cell status.

---

## Reference-data requirements

### SBM-NBP-020: PRA UK source mapping (prerequisite)

Before any additional `PRA_UK_CRR` cell is implemented:

- Keep the `regulatory_sources.yml` entry linked to PS1/26 Appendix 1 /
  PRA2026/1 and granular enough for reviewers to locate the relevant
  market-risk ASA articles.
- Use the SBM source map below to create exact-cell citation ids; generic
  profile-family citations are not sufficient for capital output.
- Record divergence from `EU_CRR3` where UK rules differ.
- Close a dedicated mapping issue referenced from traceability.

GIRR delta now satisfies this source-mapping prerequisite through Articles 325c,
325h, and 325ae-325ag. The remaining PRA cells still fail closed until their
own exact-cell source mappings, citations, reference data, and fixtures land.

Initial PRA SBM source map:

| Topic | PRA source |
| --- | --- |
| ASA scope and structure | Article 325c |
| SBM definitions and risk classes | Article 325d |
| Delta, vega, and curvature components | Article 325e |
| Delta and vega aggregation | Article 325f |
| Curvature aggregation | Article 325g |
| Correlation scenarios and final SBM selection | Article 325h |
| Index and multi-underlying treatment | Article 325i |
| Collective investment undertaking treatment | Article 325j |
| GIRR risk factors | Article 325l |
| CSR non-securitisation risk factors | Article 325m |
| CSR securitisation ACTP and non-ACTP risk factors | Article 325n |
| Equity risk factors | Article 325o |
| Commodity risk factors | Article 325p |
| FX risk factors, base-currency permission, and FX curvature scalar | Article 325q |
| Delta sensitivity formulas | Article 325r |
| Vega sensitivity formulas | Article 325s |
| Sensitivity computation requirements and alternative delta permission | Article 325t |
| Residual risk add-on boundary | Article 325u |
| GIRR delta weights/correlations | Articles 325ae-325ag |
| CSR non-sec weights/correlations | Articles 325ah-325aj |
| CSR ACTP weights/correlations | Articles 325ak-325al |
| CSR non-ACTP weights/correlations | Articles 325am-325ao |
| Equity weights/correlations | Articles 325ap-325ar |
| Commodity weights/correlations | Articles 325as-325au |
| FX weights/correlations | Articles 325av-325aw |
| Vega and curvature weights/correlations | Articles 325ax-325ay |

PRA CP16/22 Chapter 6 remains historical policy context only. PS1/26 Appendix 1
and PRA2026/1 are the final-rule authority for parameter mapping.

### SBM-NBP-020A: PRA mirroring, divergence, and effective-date policy

`PRA_UK_CRR` runtime support requires profile-owned UK citations and fixtures
even where PRA numerics appear identical to Basel MAR21 or EU CRR3. A PRA cell
may share a numerical table shape only when the implementation records:

- the exact PRA2026/1 article ids for that cell;
- any known PRA-vs-EU or PRA-vs-Basel divergence;
- `PRA_UK_CRR` profile id, PRA citation ids, and a PRA profile hash in runtime
  output;
- deterministic `*_pra_uk_crr_v1` fixture evidence.

The effective date for PRA2026/1 planning metadata is 2027-01-01. Runtime code
must not present PRA output as current production capital before that effective
date, and package documentation must continue to describe evidence as synthetic
and validation pending.

### SBM-NBP-021: U.S. NPR citation registry

For each implemented `US_NPR_2_0` cell, `PROFILE_CITATIONS[US_NPR_2_0]` must
include stable citation ids for:

- risk weights used;
- bucket definitions;
- intra- and inter-bucket correlations;
- correlation scenarios (if applicable to the measure).

Citation `location` must reference Federal Register section V.A.7.a subsections
or cited proposal tables, not generic “NPR 2.0”.

### SBM-NBP-022: EU CRR3 citation registry

For each implemented `EU_CRR3` cell, citations must use article-level ids
(e.g. `EU_CRR3_ART_325r`) suitable for cross-linking to EBA single-rulebook
pages where applicable.

### SBM-NBP-023: Profile reference payload hash

`get_sbm_rule_profile(profile)` must include non-Basel reference payloads in
the deterministic `content_hash` once that profile is partially or fully
supported. Changing NPR/EU tables without updating fixtures must fail hash tests.

### SBM-NBP-024: Missing lookup keys

Missing bucket, tenor, or risk-weight keys for a **supported** cell must raise
`SbmInputError` with field context. Missing support for an **unsupported** cell
must raise `UnsupportedRegulatoryFeatureError` before capital calculation.

---

## First-slice requirements (`US_NPR_2_0` × GIRR × DELTA)

### SBM-NBP-030: NPR GIRR delta reference data

The package must provide `US_NPR_2_0` GIRR delta:

- bucket definitions;
- tenor set;
- delta risk weights;
- special risk factors (if prescribed by NPR for GIRR);
- intra-bucket and inter-bucket correlations for delta aggregation;
- correlation scenario definitions (low/medium/high) with cited multipliers.

Data must be stored in profile-keyed structures parallel to existing
`BASEL_GIRR_*` constants.

### SBM-NBP-031: NPR GIRR delta fixture pack

Add `tests/fixtures/girr_delta_us_npr_v1/` containing:

- `manifest.json` with `profile: US_NPR_2_0`, schema version, file SHA256 hashes;
- `sensitivities.json` — synthetic rows with NPR-appropriate bucket/tenor labels;
- `expected_outputs.json` — total capital, bucket breakdown, citation ids;
- `invalid_cases.json` — at least one fail-closed case (e.g. unsupported
  curvature under NPR profile);
- `loader.py` and `README.md` following existing fixture pack conventions.

Existing `girr_delta_v1` manifest hashes must not change.

### SBM-NBP-032: NPR GIRR delta tests

Required tests for the first slice:

| Test | Requirement |
| --- | --- |
| Row-wise capital | `calculate_sbm_capital` matches fixture expected outputs |
| Reference data | NPR weight lookup returns cited ids |
| Regimes | `resolve_sbm_profile(US_NPR_2_0)` succeeds; profile hash stable |
| Support matrix | Doc and `_PHASE1_SUPPORTED` include GIRR/DELTA for NPR |
| Fail-closed | NPR GIRR vega, GIRR curvature, and all other NPR classes still raise until their slices land |
| Batch parity | Package-owned batch matches row-wise for fixture sensitivities |
| Arrow parity | Arrow batch handoff matches row-wise where adapter exists |

## Second-slice requirements (`US_NPR_2_0` × GIRR × VEGA)

### SBM-NBP-034: NPR GIRR vega reference data

The package must provide `US_NPR_2_0` GIRR vega:

- option-tenor and underlying-tenor reference data;
- liquidity-horizon and risk-weight citation ids;
- intra-bucket and inter-bucket correlation citation ids;
- correlation scenario definitions with cited multipliers.

Data must be stored in profile-keyed structures parallel to existing
`BASEL_MAR21` GIRR vega reference data. The implementation must not silently
fall back to Basel citation ids.

### SBM-NBP-035: NPR GIRR vega fixture pack

Add `tests/fixtures/girr_vega_us_npr_v1/` containing:

- `manifest.json` with `profile: US_NPR_2_0`, schema version, file SHA256 hashes;
- `sensitivities.json` with synthetic GIRR vega rows and profile-owned mapping citations;
- `expected_outputs.json` with deterministic capital, profile hash, input hash, scenario totals, bucket details, weighted sensitivities, and citation ids;
- `invalid_cases.json` covering missing option tenor plus still-unsupported NPR cells;
- `loader.py` and `README.md` following existing fixture pack conventions.

### SBM-NBP-036: NPR GIRR vega tests

Required tests for the second slice:

| Test | Requirement |
| --- | --- |
| Row-wise capital | `calculate_sbm_capital` matches fixture expected outputs |
| Reference data | NPR GIRR vega lookup returns cited ids |
| Citation hygiene | No Basel citation id appears in the NPR GIRR vega result payload |
| Support matrix | Doc and `_PHASE1_SUPPORTED` include GIRR/DELTA and GIRR/VEGA for NPR |
| Fail-closed | Non-GIRR NPR vega and curvature cells still raise until their slices land |
| Batch parity | Package-owned batch matches row-wise for fixture sensitivities |
| Arrow parity | Arrow batch handoff matches row-wise where adapter exists |

## Third-slice requirements (`US_NPR_2_0` × GIRR × CURVATURE)

### SBM-NBP-037: NPR GIRR curvature reference data

The package must provide `US_NPR_2_0` GIRR curvature:

- curvature sensitivity and risk-factor citation ids;
- up/down shock and risk-weight citation ids;
- intra-bucket and inter-bucket correlation citation ids;
- correlation scenario and branch-selection citation ids.

Data must be stored in profile-keyed structures parallel to existing
`BASEL_MAR21` GIRR curvature reference data. The implementation must not
silently fall back to Basel citation ids.

### SBM-NBP-038: NPR GIRR curvature fixture pack

Add `tests/fixtures/girr_curvature_us_npr_v1/` containing:

- `manifest.json` with `profile: US_NPR_2_0`, schema version, file SHA256 hashes;
- `sensitivities.json` with synthetic GIRR curvature rows and profile-owned mapping citations;
- `expected_outputs.json` with deterministic capital, profile hash, input hash, scenario totals, bucket details, weighted sensitivities, CVR branch records, and citation ids;
- `invalid_cases.json` covering missing up/down shocks plus still-unsupported NPR cells;
- `loader.py` and `README.md` following existing fixture pack conventions.

### SBM-NBP-039: NPR GIRR curvature tests

Required tests for the third slice:

| Test | Requirement |
| --- | --- |
| Row-wise capital | `calculate_sbm_capital` matches fixture expected outputs |
| Reference data | NPR GIRR curvature lookup returns cited ids |
| Citation hygiene | No Basel citation id appears in the NPR GIRR curvature result payload |
| Support matrix | Doc and `_PHASE1_SUPPORTED` include exactly GIRR/DELTA, GIRR/VEGA, and GIRR/CURVATURE for NPR |
| Fail-closed | Non-GIRR NPR curvature still raises |
| Batch parity | Package-owned batch matches row-wise for fixture sensitivities |
| Arrow parity | Arrow batch handoff matches row-wise where adapter exists |

### SBM-NBP-033: NPR GIRR delta CRIF (optional in first PR)

If CRIF mapping is included in the first NPR slice, it must:

- map only NPR-supported risk types;
- reject rows with explicit unsupported reasons;
- not reuse Basel-only mapping without NPR citation metadata.

CRIF omission is acceptable if documented as a follow-up; capital path must still
meet SBM-NBP-032.

## U.S. NPR FX policy requirements

### SBM-NBP-043: NPR FX reporting-currency first policy

The first `US_NPR_2_0` FX runtime slice must support reporting-currency FX risk
factors only. The policy citation ids are:

- `us_npr_91_fr_14952_va7a_fx_reporting_currency`;
- `us_npr_91_fr_14952_va7a_fx_delta_weights`;
- `us_npr_91_fr_14952_va7a_fx_delta_sqrt2`;
- `us_npr_91_fr_14952_va7a_fx_delta_intra`;
- `us_npr_91_fr_14952_va7a_fx_delta_inter`;
- `us_npr_91_fr_14952_va7a_fx_vega_option_tenors`;
- `us_npr_91_fr_14952_va7a_fx_vega_lh_rw`;
- `us_npr_91_fr_14952_va7a_fx_vega_intra`;
- `us_npr_91_fr_14952_va7a_fx_vega_inter`;
- `us_npr_91_fr_14952_va7a_fx_curvature_factors`;
- `us_npr_91_fr_14952_va7a_fx_curvature_shocks`;
- `us_npr_91_fr_14952_va7a_fx_curvature_intra`;
- `us_npr_91_fr_14952_va7a_fx_curvature_inter`;
- `us_npr_91_fr_14952_va7a_fx_curvature_scenarios`;
- `us_npr_91_fr_14952_va7a_fx_base_currency_approval`.

These ids cite Federal Register 91 FR 15020 and 91 FR 15037-15038 section V.A.7.a in
`reference_citations_us_npr.py`. The FX delta, vega, and curvature implementations must use
profile-owned NPR FX reference data and must not infer base-currency approval
from `SbmCalculationContext.base_currency`.

The `fx_delta_us_npr_v1` fixture pack records row, batch, and Arrow parity for
the reporting-currency FX delta path. The `fx_vega_us_npr_v1` and
`fx_curvature_us_npr_v1` fixture packs record row, batch, and Arrow parity for
the reporting-currency FX vega and curvature paths.

### SBM-NBP-044: NPR FX base-currency treatment fails closed

Base-currency FX treatment remains unsupported until a dedicated implementation
models all required approval evidence. `SbmRunControls.fx_risk_factor_basis`
must accept only `REPORTING_CURRENCY` in current runtime validation.
`BASE_CURRENCY_APPROVED` must raise `UnsupportedRegulatoryFeatureError` even
when `fx_base_currency_approval_ids` are supplied.

Future support for `BASE_CURRENCY_APPROVED` must add:

- prior supervisory approval identifier(s);
- the single approved base currency;
- explicit translation-risk treatment;
- profile-owned FX reference data and citation ids;
- deterministic reporting-currency and base-currency fixtures;
- fail-closed tests for missing or malformed approval evidence.

---

## Fail-closed requirements (all profiles)

### SBM-NBP-040: Unsupported cell error type

Cells marked unsupported fail-closed must raise
`UnsupportedRegulatoryFeatureError` with a message naming `profile_id`,
`risk_class`, and `risk_measure` (or profile-level reason before cell routing).

### SBM-NBP-041: No placeholder capital

Unsupported cells must not return `SbmCapitalResult` with zero total capital,
empty risk-class lists, or `unsupported_features=()` while claiming success.

### SBM-NBP-042: Public API stability

`calculate_sbm_capital`, `SbmCalculationContext`, and `SbmCapitalResult` field
names must remain backward compatible for Basel runs. New fields require ADR if
breaking.

---

## Documentation and maturity requirements

### SBM-NBP-050: Traceability updates

Each implementation PR must update:

- `packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md` (non-Basel matrix);
- `packages/frtb-sbm/docs/regulatory_sources.yml` (section hints);
- model documentation limitations if comparison profiles gain capital paths.

### SBM-NBP-051: Package maturity registry

Update `docs/quality/package_maturity.toml` only when evidence genuinely
supports a maturity change (e.g. new required test path for NPR fixtures).
Documentation-only PRs must not bump maturity.

### SBM-NBP-052: Changelog fragments

Feature PRs add `packages/frtb-sbm/changelog.d/<pr>.feat.md` (or `.docs.md` for
docs-only). No version bump in feature PRs (ADR 0015).

---

## Quality-control requirements

### SBM-NBP-060: CI gates

Implementation PRs must pass:

- `make agent-guard` (or documented cloud equivalent);
- `make quality-control`;
- `uv run pytest packages/frtb-sbm/tests`;
- unchanged Basel fixture hashes where required.

### SBM-NBP-061: Numerical materiality

If NPR (or EU) tables produce different capital than Basel for the same
synthetic inputs, an ADR is required before merge, and fixture expected values
must reflect the cited profile — not Basel shortcuts.

---

## Requirement traceability matrix

| Requirement | Current evidence | Remaining target |
| --- | --- | --- |
| SBM-NBP-001 | Met (design + traceability link; `US_NPR_2_0` and `PRA_UK_CRR` partial matrices) | Maintain in traceability |
| SBM-NBP-002 | Met for Basel, `US_NPR_2_0` GIRR delta/vega/curvature and FX delta/vega/curvature, and `PRA_UK_CRR` GIRR delta via `test_sbm_support_matrix.py` | Extend for each new cell |
| SBM-NBP-010 | Enforced for the implemented NPR GIRR delta/vega/curvature and FX delta/vega/curvature and PRA GIRR delta slices through profile-owned citations and fixture citation checks | Extend for each new cell |
| SBM-NBP-013 | Met for exact-cell PRA gating | Preserve as PRA coverage expands |
| SBM-NBP-030–039 | Met for `US_NPR_2_0` GIRR delta/vega/curvature with `girr_delta_us_npr_v1`, `girr_vega_us_npr_v1`, `girr_curvature_us_npr_v1`, and for `PRA_UK_CRR` GIRR delta with `girr_delta_pra_uk_crr_v1`; supported cells have row/batch/Arrow tests | Extend to later cells |
| SBM-NBP-043–044 | Met for NPR FX delta/vega/curvature through `fx_delta_us_npr_v1`, `fx_vega_us_npr_v1`, `fx_curvature_us_npr_v1`, reporting-currency citation ids, `SbmRunControls.fx_risk_factor_basis`, and fail-closed base-currency validation tests | Preserve as additional FX policy branches are evaluated |
| SBM-NBP-040–042 | Met for unsupported NPR cells, EU cells, and unsupported PRA cells through fail-closed tests | Preserve as coverage expands |
| SBM-NBP-060 | Required for implementation PRs | Run before push |

---

## Follow-up issue templates

Use these titles when splitting implementation work:

1. **SBM NPR non-GIRR delta** — equity, commodity, and CSR NPR mappings.
2. **SBM EU CRR3 GIRR delta** — article mapping + first EU cell (blocked on legal mapping review).
3. **SBM PRA UK CRR next cells** — SBM-NBP-020 prerequisite satisfied by
   PS1/26 Appendix 1 / PRA2026/1; GIRR delta is implemented under audit, and
   remaining runtime cells stay fail-closed until exact-cell citations,
   reference data, and fixtures land.
