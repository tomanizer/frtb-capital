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
| 2 | PRA UK CRR / PRA Rulebook (TBD) | `PRA_UK_CRR` |
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

`phase1_capital_supported_paths(profile_id)` in `validation.py` must match the
matrix for every cell marked implemented. Tests in
`tests/test_sbm_support_matrix.py` must fail if parity breaks.

### SBM-NBP-003: Source manifest linkage

Each profile family used for implementation must have an entry in
`packages/frtb-sbm/docs/regulatory_sources.yml` with `section_hint` granular
enough for reviewers to locate bucket/weight tables. `PRA_UK_CRR` may remain
absent until SBM-NBP-020 is satisfied.

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

`PRA_UK_CRR` must remain unsupported fail-closed at runtime until
SBM-NBP-020 is complete. Documentation must mark all 21 cells **blocked**, not
planned, until a PRA source mapping issue is closed.

---

## Reference-data requirements

### SBM-NBP-020: PRA UK source mapping (prerequisite)

Before any `PRA_UK_CRR` cell is implemented:

- Add `regulatory_sources.yml` entry with official PRA/UK CRR link and section
  hints for SBM tables.
- Record divergence from `EU_CRR3` where UK rules differ.
- Close a dedicated mapping issue referenced from traceability.

Until then, all PRA cells remain blocked.

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
- `invalid_cases.json` — at least one fail-closed case (e.g. unsupported vega
  under NPR profile);
- `loader.py` and `README.md` following existing fixture pack conventions.

Existing `girr_delta_v1` manifest hashes must not change.

### SBM-NBP-032: NPR GIRR delta tests

Required tests for the first slice:

| Test | Requirement |
| --- | --- |
| Row-wise capital | `calculate_sbm_capital` matches fixture expected outputs |
| Reference data | NPR weight lookup returns cited ids |
| Regimes | `resolve_sbm_profile(US_NPR_2_0)` succeeds; profile hash stable |
| Support matrix | Doc and `_PHASE1_SUPPORTED` include only GIRR/DELTA for NPR |
| Fail-closed | NPR GIRR vega/curvature and all other NPR classes still raise |
| Batch parity | Package-owned batch matches row-wise for fixture sensitivities |
| Arrow parity | Arrow batch handoff matches row-wise where adapter exists |

### SBM-NBP-033: NPR GIRR delta CRIF (optional in first PR)

If CRIF mapping is included in the first NPR slice, it must:

- map only NPR-supported risk types;
- reject rows with explicit unsupported reasons;
- not reuse Basel-only mapping without NPR citation metadata.

CRIF omission is acceptable if documented as a follow-up; capital path must still
meet SBM-NBP-032.

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
| SBM-NBP-001 | Met (design + traceability link; `US_NPR_2_0` partial matrix) | Maintain in traceability |
| SBM-NBP-002 | Met for Basel and `US_NPR_2_0` GIRR delta via `test_sbm_support_matrix.py` | Extend for each new cell |
| SBM-NBP-010 | Enforced for the implemented NPR GIRR delta slice through profile-owned citations and fixture citation checks | Extend for each new cell |
| SBM-NBP-013 | Met | Until PRA mapping issue |
| SBM-NBP-030–032 | Met for `US_NPR_2_0` GIRR delta with `girr_delta_us_npr_v1` and row/batch/Arrow tests | Extend to later NPR cells |
| SBM-NBP-040–042 | Met for unsupported NPR cells, EU, and PRA fail-closed tests | Preserve as coverage expands |
| SBM-NBP-060 | Required for implementation PRs | Run before push |

---

## Follow-up issue templates

Use these titles when splitting implementation work:

1. **SBM NPR GIRR vega/curvature** — extend NPR GIRR row (phase 2).
2. **SBM NPR non-GIRR delta** — FX, equity, commodity, and CSR NPR mappings.
3. **SBM EU CRR3 GIRR delta** — article mapping + first EU cell (blocked on legal mapping review).
4. **SBM PRA UK CRR source mapping** — SBM-NBP-020 prerequisite.
