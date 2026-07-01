# SBM regulatory traceability

## Purpose

This document maps `frtb-sbm` package code and remaining unsupported
boundaries to the regulatory paragraphs that motivate them. It is a
traceability aid for implementation and review; it is not legal advice and it
does not make unsupported or unmapped features capital-producing.

The companion source manifest is
[`docs/regulatory_sources.yml`](regulatory_sources.yml). It keeps official URLs,
section hints, status labels, and implementation-reference links without
vendoring regulatory text into the package.

Use this document in two directions:

- **Code to regulation:** start from an existing module and inspect the cited
  Basel, U.S. NPR, and EU anchors.
- **Regulation to code:** start from a regulatory topic and inspect whether the
  package implements, plans, excludes, or rejects that scope.

## Status taxonomy

| Status | Meaning in `frtb-sbm` |
| --- | --- |
| Scaffold | The package has an importable boundary and explicit failure path, but does not calculate SBM capital. |
| Planned | The behavior is issue-backed and source-mapped, but no capital-producing code exists yet. |
| Partial | Some documentation, data contract, or helper exists, but the end-to-end behavior is not complete. |
| Implemented | Tested code produces the cited behavior for supported inputs. |
| Implemented under audit | Tested code produces the cited behavior for supported inputs, but package validation remains synthetic/internal and `PACKAGE_METADATA.validation_status` is `PENDING`. |
| Excluded | The behavior belongs outside `frtb-sbm`, usually in upstream systems or suite orchestration. |
| Unsupported fail-closed | The package must raise an explicit unsupported-feature or input error until the profile or feature has cited rules and deterministic tests. |
| Out of scope | Deliberately deferred beyond the current phase boundary. |

Package maturity remains `partial_runtime` while any declared comparison profile
has unsupported cells. ADR 0048 distinguishes this package-level status from the
cell-level `Implemented under audit` status. A comparison-profile runtime gate
opens only when the exact profile/risk-class/measure cell has profile-owned
citations and deterministic fixture evidence, or an ADR-approved shared-fixture
rationale. Basel-mirrored numerics alone do not open a U.S. NPR 2.0, EU CRR3,
or PRA UK CRR cell.

## Phase-1 support status (supported Basel slices)

Parent issue: [#151](https://github.com/tomanizer/frtb-capital/issues/151).

| Area | Phase-1 status | Notes |
| --- | --- | --- |
| Package scaffold and public boundary | Implemented under audit | `calculate_sbm_capital` produces capital for supported BASEL_MAR21 delta, vega, and curvature inputs. |
| Model documentation and traceability | Implemented | Documentation pack from #152; updated with implementation status. |
| Canonical data models and validation | Implemented | #153 |
| Rule profile and GIRR delta reference data | Implemented | #154 — BASEL_MAR21 profile |
| U.S. NPR 2.0 GIRR delta comparison slice | Implemented under audit | #504 — `girr_delta_us_npr_v1` fixture pack; proposed-rule comparison material only. |
| Weighted sensitivities (supported delta and vega) | Implemented under audit | #155, #161, #162, #164, #254, #287, #288, and the #312 vectorisation sprint. |
| Intra-bucket aggregation | Implemented | #156 |
| Inter-bucket aggregation and scenario selection | Implemented | #157 |
| Public GIRR delta capital API | Implemented | #158 |
| BASEL_MAR21 Arrow/batch handoff | Implemented under audit | Arrow input converts to `SbmSensitivityBatch` for supported delta, vega, and curvature paths; kernels remain NumPy-native. #269 adds a CRIF-to-Arrow entry path for GIRR delta. #285 generalises the package-owned batch foundation; #286-#289 add early migrated paths; #312 completes the supported-path vectorisation sprint. |
| Audit/replay and synthetic fixtures | Implemented | #159 — `girr_delta_v1` fixture pack |
| Vega capital (GIRR) | Implemented | #161 — `girr_vega_v1` fixture pack |
| Vega capital (FX, equity, commodity, and CSR) | Implemented under audit | #254 adds BASEL_MAR21 vega support under MAR21.90-MAR21.95; the #312 vectorisation sprint adds Arrow/batch handoffs. |
| FX delta capital | Implemented | #162 — `fx_delta_v1` fixture pack, MAR21.86-MAR21.89 |
| Curvature capital | Implemented under audit | #252 added the GIRR MAR21.5 branch engine. #253 adds MAR21.96-MAR21.101 reference weights/correlations and public capital for GIRR, FX, equity, commodity, CSR non-sec, CSR sec non-CTP, and CSR sec CTP under BASEL_MAR21. The #312 vectorisation sprint adds Arrow/batch handoffs. Unsupported sub-features, such as equity repo curvature, fail closed. |
| Curvature contracts | Implemented under audit | #165 added up/down shock contracts. Row-wise, package-owned batch, and Arrow batch paths preserve separate up/down shock arrays for supported BASEL_MAR21 curvature inputs. |
| Equity delta capital | Implemented | `equity_delta_v1` fixture pack, MAR21.71–MAR21.75. |
| Commodity delta capital | Implemented | `commodity_delta_v1` fixture pack, MAR21.76–MAR21.80. |
| CSR non-securitisation delta capital | Implemented | #164 — `csr_nonsec_delta_v1` fixture pack, MAR21.51–MAR21.57. |
| CSR securitisation (CTP / non-CTP) | Implemented | MAR21.58-MAR21.70 supported under BASEL_MAR21, including CTP decomposition-evidence fail-closed checks. |
| CRIF/CSV adapters | Implemented | Row-dict compatibility maps supported BASEL_MAR21 delta, vega, and curvature CRIF risk types to canonical `SbmSensitivity` rows with auditable rejects. #269 adds shared CRIF-to-Arrow normalization plus SBM-owned GIRR delta RiskType mapping. |
| SA composition | Excluded | Belongs in `frtb-orchestration`. |
| Analytical Euler attribution | Implemented for supported delta/vega branches | `calculate_sbm_attribution` emits shared `CapitalContribution` records using analytical Euler derivatives for selected, differentiable delta and vega branches. Curvature, active floors, alternative `S_b`, missing scenario detail, and incomplete pairwise evidence emit explicit `UNSUPPORTED` residual records under ADR 0038. `calculate_sbm_capital_impact` emits finite-difference baseline-vs-candidate impact records and is not presented as marginal contribution. |

No document or test in this package should describe outputs as final regulatory
capital. U.S. NPR 2.0 material is proposed-rule comparison only.

## BASEL_MAR21 risk-class/measure support matrix

This table is the documentation source for `phase1_capital_supported_paths()` in
`validation/context.py`, `PROFILE_SUPPORTED_MEASURES` in `regimes.py`, and the
row, batch, and Arrow batch dispatchers in `capital.py` and `arrow_batch.py`.

| Risk class | Delta | Vega | Curvature | Runtime notes |
| --- | --- | --- | --- | --- |
| GIRR | implemented but under audit | implemented but under audit | implemented but under audit | GIRR delta/vega use cited tenor, bucket, and scenario data; curvature uses MAR21.5 and MAR21.96-MAR21.101 branch mechanics. |
| FX | implemented but under audit | implemented but under audit | implemented but under audit | FX curvature MAR21.98 non-reporting-currency scalar requires explicit `FX_CURVATURE_SCALAR_1_5_FLAG` evidence. |
| Equity | implemented but under audit | implemented but under audit | implemented but under audit | Equity repo vega/curvature sub-features remain unsupported fail-closed until separately cited and tested. |
| Commodity | implemented but under audit | implemented but under audit | implemented but under audit | Commodity vega and curvature share the package-owned batch and Arrow batch boundary. |
| CSR non-securitisation | implemented but under audit | implemented but under audit | implemented but under audit | CSR non-sec delta/vega/curvature use MAR21.51-MAR21.57 and shared vega/curvature mechanics. |
| CSR securitisation non-CTP | implemented but under audit | implemented but under audit | implemented but under audit | Cited securitisation reference tables and branch metadata are retained. |
| CSR securitisation CTP | implemented but under audit | implemented but under audit | implemented but under audit | CTP decomposition evidence remains fail-closed when the required mapping evidence is absent. |

`Implemented but under audit` means the package has deterministic synthetic
tests and public entrypoints, but no independent model-validation pack. These
outputs are not final regulatory capital.

## Non-Basel profile boundary

Design and normative requirements for expanding comparison profiles:
[`docs/modules/frtb-sbm/NON_BASEL_PROFILE_DESIGN.md`](../../../docs/modules/frtb-sbm/NON_BASEL_PROFILE_DESIGN.md)
and
[`docs/modules/frtb-sbm/NON_BASEL_PROFILE_REQUIREMENTS.md`](../../../docs/modules/frtb-sbm/NON_BASEL_PROFILE_REQUIREMENTS.md).

| Profile | Current runtime status | Planning status |
| --- | --- | --- |
| `US_NPR_2_0` | partial (1 / 21 cells) | GIRR delta implemented under audit; all other cells unsupported fail-closed. Proposed-rule material only. |
| `EU_CRR3` | unsupported fail-closed (0 / 21 cells) | planned after article-level mapping (Regulation (EU) 2024/1623, Arts. 325e-325az). |
| `PRA_UK_CRR` | unsupported fail-closed (0 / 21 cells) | blocked pending PRA/UK CRR SBM source mapping (see SBM-NBP-020). |

Except for `US_NPR_2_0` GIRR delta, every risk-class and measure combination for
non-Basel profiles remains unsupported fail-closed. Basel MAR21 sub-features that
are unsupported within `BASEL_MAR21` (for example equity repo vega/curvature)
are documented in the BASEL matrix above, not as non-Basel backlog.

### Comparison-profile risk-class/measure matrix

`US_NPR_2_0` GIRR delta is fixture-backed by `girr_delta_us_npr_v1` and carries
U.S. NPR profile-owned citation ids. All other entries in this table fail closed
before capital is emitted.

| Risk class | `US_NPR_2_0` delta | `US_NPR_2_0` vega | `US_NPR_2_0` curvature | `EU_CRR3` delta | `EU_CRR3` vega | `EU_CRR3` curvature | `PRA_UK_CRR` delta | `PRA_UK_CRR` vega | `PRA_UK_CRR` curvature |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GIRR | implemented under audit | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed |
| FX | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed |
| Equity | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed |
| Commodity | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed |
| CSR non-securitisation | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed |
| CSR securitisation non-CTP | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed |
| CSR securitisation CTP | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed | unsupported fail-closed |

## Closed-issue audit

| Issue | Closed scope | #256 conclusion |
| --- | --- | --- |
| #160 | Parent follow-on for vega, curvature, remaining risk classes, adapters, and orchestration. | Not a missed runtime item: it correctly identified the follow-on work. The missing artifact was a consolidated status matrix after the children and later vectorisation sprint landed. |
| #161 | Cited vega scaling and vega capital support. | Partially superseded by later delivery: GIRR vega closed first, non-GIRR vega was completed by #254, and Arrow/batch vega handoffs were completed by the #312 vectorisation sprint. |
| #166 | Curvature capital path. | Partially superseded by later delivery: GIRR branch mechanics and curvature contracts landed first; #252 and #253 completed BASEL_MAR21 cross-class curvature capital, and #312 added Arrow/batch handoffs. |
| #169 | CRIF adapters, orchestration handoff, performance controls, and attribution/impact readiness items. | Not an incorrectly implemented SBM capital item. CRIF row adapters cover supported delta/vega/curvature mappings; only GIRR delta has a CRIF-to-Arrow high-volume path, which remains an adapter boundary rather than a capital-kernel gap. |
| #226 | Architecture and status documentation drift. | Partially identified the drift, but did not add the SBM-specific support matrix or closed-issue audit required here. |
| #244 | Suite aggregation priority for SBM curvature and orchestration. | Delivered downstream orchestration consumption after SBM emitted delta, vega, and curvature results. It did not replace the need for this package-local support matrix. |

## Source register

| Source family | Primary references used by this package | Package status |
| --- | --- | --- |
| Basel Standardised Approach | Basel Framework MAR20 and MAR21. MAR20.4 places SBM in the SA stack. MAR21.1-MAR21.101 define risk classes, measures, weights, buckets, and aggregation. | Implemented for supported phase-1 Basel slices. |
| U.S. NPR 2.0 | Federal Register 91 FR 14952, March 27, 2026. Section V.A.7.a defines the standardized non-default process. | Partial comparison profile: GIRR delta implemented under audit; proposed-rule material only. |
| EU CRR3 | Regulation (EU) 2024/1623 Articles 325e-325az. | Planned comparison profile; EU CRR3 runtime cells fail closed until article-level mappings and deterministic fixtures are added. |
| PRA UK CRR | PRA/UK CRR source mapping not yet present for SBM. | Blocked comparison profile; all PRA UK CRR runtime cells fail closed until `SBM-NBP-020` adds source mappings and fixtures. |
| ISDA CRIF | CRIF field convention. | Adapter inspiration only; not a regulatory source. |

Use `docs/regulatory_sources.yml` for topic-level links and review notes.

## Primary-source links

- Basel Framework MAR20, Standardised approach:
  https://www.bis.org/basel_framework/chapter/MAR/20.htm
- Basel Framework MAR21, Sensitivities-based method:
  https://www.bis.org/basel_framework/chapter/MAR/21.htm
- U.S. NPR 2.0 / Federal Register 91 FR 14952:
  https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959
- Regulation (EU) 2024/1623 (CRR3):
  https://eur-lex.europa.eu/eli/reg/2024/1623/oj/eng

## Code to regulation

| Module | Responsibility | Basel reference | U.S. NPR 2.0 reference | Current boundary |
| --- | --- | --- | --- | --- |
| `scaffold.py` | Public calculation boundary, package metadata, and delegation to `capital.py`. | MAR20.4 SA component context. | Section V.A.7.a package-scope context. | Implemented under audit — supported BASEL_MAR21 delta, vega, and curvature slices only. |
| `_version.py` | Package code-version identity for audit records. | MAR21 calculation traceability context. | Section V.A.7.a step traceability context. | Implemented for package identity only. |
| `__init__.py` | Stable package export boundary. | MAR20.4 SA component context. | Section V.A.7.a package-scope context. | Implemented public surface for supported BASEL_MAR21 delta, vega, curvature, batch, and Arrow batch paths plus the `US_NPR_2_0` GIRR delta comparison slice. |
| `data_models.py` | Frozen sensitivity, context, weighted sensitivity, bucket, risk-class, and result dataclasses. | MAR21.1-MAR21.8. | Section V.A.7.a steps one through three. | Implemented (#153). |
| `batch.py` | Package-owned NumPy-backed homogeneous sensitivity batch and row-equivalent input hashing. | MAR21.4-MAR21.7, MAR21 risk-class-specific weighting provisions. | Section V.A.7.a steps three through six. | Implemented under audit for supported BASEL_MAR21 delta, vega, and curvature paths. |
| `validation/context.py` | Input invariants, profile gates, supported-path checks, and explicit package input errors. | MAR21 risk-factor assignment context. | Section V.A.7.a steps one and two. | Implemented (#153). |
| `regimes.py` | Rule-profile identity, support declarations, unsupported-profile guardrails, and deterministic profile hash. | MAR21 profile for Basel SBM mechanics. | Section V.A.7.a U.S. profile. | Implemented under audit for BASEL_MAR21 supported delta/vega/curvature slices and `US_NPR_2_0` GIRR delta; unsupported comparison-profile cells fail closed. |
| `reference_data.py` | Risk-class bucket definitions, tenor sets, risk weights, correlations, scenario labels, and citation ids. | MAR21 risk-class tables, including MAR21.90-MAR21.95 vega and MAR21.96-MAR21.101 curvature weights and correlations. | Section V.A.7.a risk-weight and correlation steps. | Implemented for BASEL_MAR21 GIRR, FX, equity, commodity, and CSR delta/vega/curvature reference data plus profile-owned `US_NPR_2_0` GIRR delta data. |
| `csr_nonsec_reference_data.py` | CSR non-sec buckets, weights, intra/inter correlations, and validation helpers. | MAR21.51-MAR21.57. | Section V.A.7.a CSR non-sec context. | Implemented (#164). |
| `weighted_sensitivity.py` | Cited risk-weight lookup and weighted sensitivity records for supported measures. | MAR21 risk-weight provisions by class. | Section V.A.7.a step three. | Implemented for supported delta/vega row and batch weighting. Curvature branch weighting lives in `curvature.py`. |
| `aggregation.py` | Shared intra-bucket and inter-bucket aggregation, scenario evaluation, and floors. | MAR21 aggregation formulas. | Section V.A.7.a steps four through six. | Implemented (#156, #157). |
| `capital.py` | Public calculation entry point wiring validation, profiles, weighting, aggregation, and result assembly. | MAR21 end-to-end SBM mechanics. | Section V.A.7.a full process. | Implemented under audit for supported BASEL_MAR21 delta/vega/curvature row and batch entrypoints, `US_NPR_2_0` GIRR delta row/batch/Arrow entrypoints, and portfolio batch dispatch. |
| `risk_classes/vega.py` | Non-GIRR vega aggregation for FX, equity, commodity, CSR non-sec, CSR sec CTP, and CSR sec non-CTP. | MAR21.90-MAR21.95. | Section V.A.7.a vega context. | Implemented with Table 13 liquidity horizons, MAR21.94 delta-rho-times-option-rho correlations, MAR21.95 delta gamma reuse, batch path support, and explicit equity repo vega fail-closed behavior. |
| `arrow_batch.py` | Adapter boundary from normalized Arrow batch to package-owned SBM batches. | MAR21 risk-factor assignment and weighting context. | Section V.A.7.a tabular input context. | Implemented under audit for supported BASEL_MAR21 delta, vega, and curvature handoffs; no Arrow in kernels. Benchmark evidence records that migrated high-volume paths avoid accepted-row dataclasses. |
| `curvature.py` | Curvature input contracts, up/down shock validation, CVR+/CVR- factor netting, FX MAR21.98 scalar marking, bucket branch selection, squared curvature correlations, and bucket branch audit records. | MAR21.5 and MAR21.96-MAR21.101 curvature provisions. | Section V.A.7.a footnote 328. | Implemented under audit for BASEL_MAR21 curvature capital across supported SBM risk classes, with row, batch, and Arrow batch entrypoints. |
| `attribution.py` | Analytical Euler contribution projection and unsupported residual records. | MAR21.4(4)-MAR21.4(5) delta/vega aggregation; MAR21.5 curvature floor boundary. | Section V.A.7.a aggregation context only. | Implemented for selected differentiable delta/vega branches; curvature and non-differentiable or incomplete-evidence branches are explicit unsupported residuals. |
| `impact.py` | Baseline-vs-candidate capital impact record. | MAR21 capital comparison context only. | Section V.A.7.a capital comparison context only. | Implemented as finite difference under ADR 0038; not a marginal contribution method. |
| `risk_classes/fx.py` | FX delta assembly onto shared aggregation primitives. | MAR21.14, MAR21.86-MAR21.89. | Section V.A.7.a FX delta context. | Implemented (#162). |
| `risk_classes/equity.py` | Equity delta assembly onto shared aggregation primitives. | MAR21.12, MAR21.71-MAR21.80. | Section V.A.7.a equity delta context. | Implemented with batch entrypoint (#287). |
| `risk_classes/commodity.py` | Commodity delta assembly onto shared aggregation primitives. | MAR21.13, MAR21.81-MAR21.85. | Section V.A.7.a commodity delta context. | Implemented with batch entrypoint (#287). |
| `risk_classes/csr_nonsec.py` | CSR non-securitisation delta assembly onto shared aggregation primitives. | MAR21.9, MAR21.51-MAR21.57. | Section V.A.7.a CSR non-sec context. | Implemented with batch entrypoint (#164, #288). |
| `risk_classes/csr_sec_nonctp.py` | CSR securitisation non-CTP delta assembly onto shared aggregation primitives. | MAR21.10, MAR21.61-MAR21.70. | Section V.A.7.a CSR securitisation context. | Implemented with batch entrypoint (#288). |
| `risk_classes/csr_sec_ctp.py` | CSR securitisation CTP delta assembly and decomposition-evidence fail-closed checks. | MAR21.11, MAR21.58-MAR21.60. | Section V.A.7.a CSR securitisation context. | Implemented with batch entrypoint (#288). |
| `audit.py` | Result serialization, input/profile hashes, scale-aware pairwise-correlation evidence summaries, and reconciliation checks. | MAR21 component traceability by formula. | Section V.A.7.a audit context. | Implemented (#159, #265). |
| `crif.py` | Optional CRIF-to-canonical mapping and GIRR delta CRIF-to-Arrow batch with rejected rows. | MAR21 risk-type mapping context only. | Section V.A.7.a canonical field mapping context. | Implemented for supported BASEL_MAR21 row-dict delta, vega, and curvature mappings; GIRR delta Arrow batch remains the high-volume CRIF path. |

## Cross-links

| Document | Location |
| --- | --- |
| Module planning pack | [`docs/modules/frtb-sbm/README.md`](../../../docs/modules/frtb-sbm/README.md) |
| Requirements registry | [`requirements/BASEL_FRTB_SBM.yml`](requirements/BASEL_FRTB_SBM.yml) |
| Regulatory assumptions | [`REGULATORY_ASSUMPTIONS.md`](REGULATORY_ASSUMPTIONS.md) |
| Package README | [`../README.md`](../README.md) |
| Issue breakdown | [`docs/modules/frtb-sbm/ISSUE_BREAKDOWN.md`](../../../docs/modules/frtb-sbm/ISSUE_BREAKDOWN.md) |
