# SBM non-Basel profile expansion — design

Parent backlog: [#501](https://github.com/tomanizer/frtb-capital/issues/501)  
Source audit: [#492](https://github.com/tomanizer/frtb-capital/issues/492)  
Detailed requirements: [NON_BASEL_PROFILE_REQUIREMENTS.md](NON_BASEL_PROFILE_REQUIREMENTS.md)

## Problem statement

`frtb-sbm` implements cited **BASEL_MAR21** delta, vega, and curvature capital
for all seven SBM risk classes (21 profile/risk-class/measure cells). The
comparison profiles `US_NPR_2_0`, `EU_CRR3`, and `PRA_UK_CRR` now expose all 21
runtime gates with Basel-mirrored numerics and profile-owned citation routing.
Each profile has one GIRR delta fixture pack; remaining cells are gated without
per-cell fixture evidence until independently transcribed.

This design records the current boundary, defines a normative support matrix,
and sequences follow-on work without changing public API semantics or Basel
fixture hashes.

## Research summary (current codebase)

### What is implemented today

| Layer | BASEL_MAR21 | Non-Basel profiles |
| --- | --- | --- |
| `SbmRegulatoryProfile` enum | `BASEL_MAR21` | `US_NPR_2_0`, `EU_CRR3`, `PRA_UK_CRR` |
| `phase1_capital_supported_paths()` | 21 cells (7×3) | 21 cells each (comparison slice) |
| `resolve_sbm_profile()` / `get_sbm_rule_profile()` | Supported | All three comparison profiles supported |
| `PROFILE_*` reference-data maps | Populated | Basel-mirrored via `mirror_with_profile_citation()` |
| Fixture packs under `tests/fixtures/` | 7 packs (`*_v1`) | `girr_delta_{us_npr,eu_crr3,pra_uk_crr}_v1` |
| `REGULATORY_TRACEABILITY.md` | Full 7×3 matrix | Comparison slice matrix with honest fixture counts |
| Enforcement tests | `test_sbm_support_matrix.py`, profile GIRR delta tests | Gate parity + no Basel citation leakage |

Authoritative runtime gates:

- `packages/frtb-sbm/src/frtb_sbm/validation/context.py` — `_PHASE1_SUPPORTED`
- `packages/frtb-sbm/src/frtb_sbm/regimes.py` — `PROFILE_SUPPORTED_MEASURES`
- `packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md` — documentation source for tests

### Basel sub-features still unsupported (within BASEL_MAR21)

These are **not** non-Basel gaps; they are explicit fail-closed cells inside the
Basel profile and must remain documented separately:

| Cell / feature | Status | Notes |
| --- | --- | --- |
| Equity `REPO` vega | Unsupported fail-closed | `weighted_sensitivity.py`, `test_sbm_non_girr_vega.py` |
| Equity `REPO` curvature | Unsupported fail-closed | `test_curvature.py`, CRIF rejects |

### Sibling package precedent (`frtb-drc`)

`frtb-drc` implements partial multi-profile support with profile-owned citations
and fail-closed cells where mappings are incomplete. SBM comparison profiles
follow the same isolation principle: no silent fallback to Basel tables when a
non-Basel profile is selected.

### Regulatory source mapping (link-only in repo)

| Profile | Primary source | Package status |
| --- | --- | --- |
| `US_NPR_2_0` | [91 FR 14952](https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959) Section V.A.7.a | Comparison slice; proposed-rule material only |
| `EU_CRR3` | [Regulation (EU) 2024/1623](https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng) Articles 325e–325az | Comparison slice |
| `PRA_UK_CRR` | [PRA PS1/26](https://www.bankofengland.co.uk/prudential-regulation/publication/2026/january/implementation-of-the-basel-3-1-final-rules-policy-statement) + [UK CRR Ch. 1a](https://www.legislation.gov.uk/eur/2013/575/part/THREE/title/IV/chapter/1a) | Comparison slice; see [`pra-uk-crr-source-mapping-status.md`](../../regulatory/profiles/pra-uk-crr-source-mapping-status.md) |

U.S. NPR 2.0 material is **proposed-rule comparison only**; comparison-slice
outputs must not be described as final regulatory capital.

## Normative support matrix

Status labels match `REGULATORY_TRACEABILITY.md`:

| Status | Meaning |
| --- | --- |
| **Implemented under audit** | Cited runtime path + synthetic fixture per cell; `ValidationStatus.PENDING` |
| **Comparison slice under audit** | All 21 runtime gates open; Basel-mirrored numerics; ≥1 GIRR delta fixture; remaining cells lack per-cell fixtures |
| **Unsupported fail-closed** | Explicit error before capital calculation |
| **Blocked** | Cannot implement until regulatory source mapping is agreed |
| **Out of scope** | Belongs outside `frtb-sbm` |

### Profile × risk-class × measure (21 cells per profile)

| Profile | Runtime gates | Fixture-backed cells | Numerics source |
| --- | ---: | ---: | --- |
| `BASEL_MAR21` | 21 / 21 | 7 risk-class packs | Basel MAR21 tables |
| `US_NPR_2_0` | 21 / 21 | 1 / 21 (GIRR delta) | Basel mirror + NPR citation ids |
| `EU_CRR3` | 21 / 21 | 1 / 21 (GIRR delta) | Basel mirror + EU article citation ids |
| `PRA_UK_CRR` | 21 / 21 | 1 / 21 (GIRR delta) | Basel mirror + UK article citation ids |

Per-class detail for non-Basel profiles (all measures share **comparison slice
under audit** until a per-cell fixture lands):

| Risk class | `US_NPR_2_0` | `EU_CRR3` | `PRA_UK_CRR` |
| --- | --- | --- | --- |
| GIRR | comparison slice under audit (`girr_delta_*_v1`) | comparison slice under audit | comparison slice under audit |
| FX | comparison slice under audit | comparison slice under audit | comparison slice under audit |
| Equity | comparison slice under audit | comparison slice under audit | comparison slice under audit |
| Commodity | comparison slice under audit | comparison slice under audit | comparison slice under audit |
| CSR non-sec | comparison slice under audit | comparison slice under audit | comparison slice under audit |
| CSR sec non-CTP | comparison slice under audit | comparison slice under audit | comparison slice under audit |
| CSR sec CTP | comparison slice under audit | comparison slice under audit | comparison slice under audit |

## Architecture design

### Design principles

1. **Profile-owned parameters** — Weights, buckets, and citations keyed by
   `SbmRegulatoryProfile`; kernels stay profile-agnostic.
2. **Fail closed** — Missing profile data raises `UnsupportedRegulatoryFeatureError`;
   never default to Basel MAR21 at runtime.
3. **Honest comparison slice** — Basel-mirrored numerics are permitted for
   cross-jurisdiction review when citation ids and docs state the limitation.
4. **Deterministic evidence** — Each newly supported cell gets a versioned
   fixture pack; GIRR delta fixtures exist per comparison profile today.
5. **Stable public API** — Profile selection remains `SbmCalculationContext.profile_id`.

### Citation id convention

| Pattern | Example | Use |
| --- | --- | --- |
| `us_npr_91_fr_14952_va7a_*` | `us_npr_91_fr_14952_va7a_girr_delta_weights` | U.S. NPR comparison slice (`va7a` = internal Section V.A.7.a shorthand) |
| `eu_crr3_art_325r_*` | `eu_crr3_art_325r_girr_delta_weights` | EU CRR3 article crosswalk |
| `pra_uk_crr_art_325r_*` | `pra_uk_crr_art_325r_girr_delta_weights` | UK CRR article crosswalk |
| `basel_mar21_*` | (existing) | Basel only |

Auto-generated comparison citations prefix Basel notes with
"Basel-mirrored numerics with profile-owned citation routing".

## Phased delivery plan

| Phase | Scope | Status |
| --- | --- | --- |
| **1** | `US_NPR_2_0` GIRR delta fixture | Delivered (`girr_delta_us_npr_v1`) |
| **2** | Full comparison-slice gates for US/EU/PRA | Delivered (21/21 runtime gates) |
| **3** | Per-cell fixtures for remaining 20 cells per profile | Planned under #501 |
| **4** | Independent NPR/EU/UK table transcription where numerics diverge | Planned; requires legal review |
| **5** | PRA Rulebook paragraph mapping for UK-specific divergences | Planned follow-on |

## Open questions / follow-up issues

1. **NPR table transcription** — Confirm GIRR bucket/weight tables at 91 FR
   Section V.A.7.a against legal review; update mirrors where NPR diverges.
2. **PRA Rulebook mapping** — Replace article-stub links with PRA Rulebook
   paragraph ids when UK-specific tables diverge from EU.
3. **Equity repo under NPR** — Until cited, remain fail-closed under all profiles.

## Acceptance mapping (AUDIT-IMP-003)

| Criterion | Status |
| --- | --- |
| Support matrix in docs | Delivered in traceability + this doc |
| ≥1 non-Basel cell per profile | GIRR delta fixtures for US/EU/PRA |
| Unsupported cells fail closed | Equity repo + unknown profiles tested |
| Basel hashes unchanged | Enforced in CI |
| No silent Basel fallback | Profile-owned maps + leakage tests |