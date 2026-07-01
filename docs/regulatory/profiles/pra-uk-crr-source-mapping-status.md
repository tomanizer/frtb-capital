# PRA UK CRR profile source-mapping status

Canonical status for the `PRA_UK_CRR` profile across capital packages. Parent
audit: [#507](https://github.com/tomanizer/frtb-capital/issues/507). Suite regime
calendar: [`../regimes/uk-pra-basel-3-1.yml`](../regimes/uk-pra-basel-3-1.yml).

This document is traceability and governance only. It is not legal advice and
does not make placeholder sources capital-producing.

## Shared status vocabulary

| Status label | Meaning |
| --- | --- |
| `mapped_and_cited` | Official source mapped to code or reference data with section-level citations and deterministic tests. |
| `comparison_only` | Policy parameters or metrics exposed for cross-jurisdiction review without producing UK capital. |
| `placeholder_reference` | Link-only manifest entry; no section-level UK mapping yet. Runtime must not treat this as capital authority. |
| `unsupported_fail_closed` | Profile or feature identity exists, but capital paths raise `UnsupportedRegulatoryFeatureError` until mapping and fixtures land. |
| `out_of_scope` | Owned outside the package (orchestration, upstream engines, approval workflows). |

`placeholder_reference` in a source manifest always pairs with
`unsupported_fail_closed` for capital runtime until the placeholder is replaced
by `mapped_and_cited` entries and fixture-backed tests.

## Profile runtime summary

| Package | Profile enum | Policy retrieval | Capital runtime | Primary guard |
| --- | --- | --- | --- | --- |
| `frtb-ima` | `PRA_UK_CRR` | Allowed (`get_policy`) | `mapped_and_cited` partial runtime | `tests/fixtures/ima_pra` replay; RFET/NMRF/IMCC capital for supported synthetic inputs |
| `frtb-sbm` | `PRA_UK_CRR` | Allowed (`resolve_sbm_profile`) | `mapped_and_cited` partial runtime | GIRR delta supported with PRA-owned Articles 325c, 325h, and 325ae-325ag citation ids plus `girr_delta_pra_uk_crr_v1`; all other PRA SBM cells remain fail-closed. |
| `frtb-drc` | `PRA_UK_CRR` | Allowed (`get_rule_profile`) | `unsupported_fail_closed` | `ensure_risk_class_supported` raises for non-securitisation, securitisation non-CTP, and CTP until #1004-#1006 land |
| `frtb-rrao` | `PRA_UK_CRR` | Allowed (`resolve_rrao_profile`) | `mapped_and_cited` partial runtime | `tests/fixtures/rrao_pra` replay; investment-fund paths remain fail-closed |

Do not implement PRA capital by silently reusing Basel, U.S. NPR, or EU defaults.
UK/PRA runtime support requires package-local citations and fixtures per
component.

## IMA inventory (`packages/frtb-ima`)

| Location | Classification | Notes |
| --- | --- | --- |
| `docs/regulatory_sources.yml` UK CRR / PRA entries | `mapped_and_cited` | Articles 325be, 325bk, retained DR 2022/2059/2060, PRA PS1/26. |
| `tests/fixtures/ima_pra/` | `mapped_and_cited` | Deterministic PRA_UK_CRR capital replay pack. |
| `src/frtb_ima/regimes.py` `_pra_uk_crr_policy` | `mapped_and_cited` partial | UK citations on policy parameters; explicit unsupported-feature gaps remain. |
| `src/frtb_ima/rfet_evidence.py` | `mapped_and_cited` | RFET assessment enabled for PRA without U.S. Type A/B taxonomy gate. |
| `src/frtb_ima/nmrf.py` | `mapped_and_cited` | BASEL_EU_NMRF routing and SES aggregation for PRA profile. |
| `src/frtb_ima/pla.py` EU/PRA Spearman path | `comparison_only` | KS + Spearman thresholds cited for EU RTS comparison; not UK capital. |
| Fed NPR / ECB comparison tests | `out_of_scope` | Other profiles remain governed by their own rows. |

## DRC inventory (`packages/frtb-drc`)

| Location | Classification | Notes |
| --- | --- | --- |
| `docs/regulatory/sources.yml` `uk_pra_ps1_26_basel_3_1_final_rules` | `placeholder_reference` | Policy-statement anchor for UK Basel 3.1 market-risk final rules; not enough by itself to emit DRC capital. |
| `docs/regulatory/sources.yml` `uk_pra_2026_1_market_risk_part` | `placeholder_reference` | Link-only PRA Rulebook legal-instrument source for Market Risk Part Articles 325v-325ad. |
| `src/frtb_drc/regime_citations_eu_pra.py` `PRA_DRC_ARTICLE_325V` | `placeholder_reference` | DRC scope source-map id for future PRA implementation. |
| `src/frtb_drc/regime_citations_eu_pra.py` `PRA_DRC_ARTICLE_325W`, `PRA_DRC_ARTICLE_325X`, `PRA_DRC_ARTICLE_325Y` | `placeholder_reference` | Non-securitisation source-map ids for gross JTD/LGD, netting/maturity, bucket/risk-weight/HBR/category mechanics. |
| `src/frtb_drc/regime_citations_eu_pra.py` `PRA_DRC_ARTICLE_325Z`, `PRA_DRC_ARTICLE_325AA` | `placeholder_reference` | Securitisation non-CTP source-map ids for gross/net JTD and bucket/risk-weight/category mechanics. |
| `src/frtb_drc/regime_citations_eu_pra.py` `PRA_DRC_ARTICLE_325AB`, `PRA_DRC_ARTICLE_325AC`, `PRA_DRC_ARTICLE_325AD` | `placeholder_reference` | CTP source-map ids for scope/gross JTD, netting/replication/decomposition, bucket/risk-weight/category mechanics. |
| `src/frtb_drc/regimes.py` `_PRA_UK_CRR_PROFILE` | `unsupported_fail_closed` | Profile metadata is available, but `supported_risk_classes` is empty by design. |
| `docs/modules/frtb-drc/PROFILE_SUPPORT_MATRIX.md` | `unsupported_fail_closed` | Lists precise source-map ids and implementation next steps for #1004, #1005, and #1006. |
| PRA DRC fixture packs | `unsupported_fail_closed` | No `drc_pra_*` replay fixture exists yet; future child issues must add deterministic fixtures before enabling runtime support. |

The DRC PRA source-map ids are not capital authority by themselves. A child
issue must promote a cell only when the implementation adds profile-owned
reference data, deterministic fixtures, citation propagation, support-matrix
updates, and fail-closed tests for the still-unsupported cells.

## RRAO inventory (`packages/frtb-rrao`)

| Location | Classification | Notes |
| --- | --- | --- |
| `docs/regulatory_sources.yml` UK CRR / retained RTS entries | `mapped_and_cited` | legislation.gov.uk URLs for Article 325u and retained DR 2022/2328. |
| `tests/fixtures/rrao_pra/` | `mapped_and_cited` | Deterministic `PRA_UK_CRR` capital replay pack. |
| `src/frtb_rrao/reference_data.py` `PRA_UK_CRR_*` maps | `mapped_and_cited` | UK citation IDs and reason codes; EU-shared exclusion enums with UK citations. |
| `src/frtb_rrao/regimes.py` `PRA_UK_CRR` metadata | `mapped_and_cited` | Supported profile with effective date 2027-01-01. |
| Investment fund inclusion paths | `unsupported_fail_closed` | Empty `PROFILE_INVESTMENT_FUND_RULES` for PRA, same as EU. |

## SBM inventory (`packages/frtb-sbm`)

| Location | Classification | Notes |
| --- | --- | --- |
| `packages/frtb-sbm/docs/regulatory_sources.yml` `uk_pra_ps1_26_sbm_asa` | `mapped_and_cited` partial | PS1/26 Appendix 1 / PRA2026/1 Articles 325c-325ay mapped to SBM planning topics; Articles 325c, 325h, and 325ae-325ag are used by the GIRR delta runtime slice. |
| `packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md` PRA rows | `mapped_and_cited` partial | `PRA_UK_CRR` GIRR delta is implemented under audit; PRA vega, curvature, and non-GIRR cells remain runtime fail-closed. |
| `src/frtb_sbm/regimes.py` `PRA_UK_CRR` metadata | `mapped_and_cited` partial | Profile resolution succeeds with 2027-01-01 effective date and GIRR delta only in `PROFILE_SUPPORTED_MEASURES`. |
| `packages/frtb-sbm/tests/fixtures/girr_delta_pra_uk_crr_v1/` | `mapped_and_cited` | Deterministic PRA_UK_CRR GIRR delta row/batch/Arrow replay pack. |

## Follow-up implementation issues (not in #507 scope)

1. [#512](https://github.com/tomanizer/frtb-capital/issues/512) — IMA PRA RFET,
   NMRF, and capital-runtime enablement with `ima_pra` fixtures (delivered).
2. [#513](https://github.com/tomanizer/frtb-capital/issues/513) — RRAO PRA
   Article 325u mapping and `rrao_pra` fixtures (delivered).
3. [#1046](https://github.com/tomanizer/frtb-capital/issues/1046) — SBM PRA UK
   CRR comparison-profile expansion roadmap.
4. [#1064](https://github.com/tomanizer/frtb-capital/issues/1064) — SBM PRA
   source-map documentation and manifest update.
5. [#1000](https://github.com/tomanizer/frtb-capital/issues/1000) — DRC
   promotion roadmap. PRA DRC runtime work is split into #1004
   non-securitisation, #1005 securitisation non-CTP, and #1006 CTP.

## Crosswalk pointers

- [`docs/regulatory/crosswalk/frtb-ima.yml`](../crosswalk/frtb-ima.yml)
- [`packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md`](../../../packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md)
- [`docs/regulatory/crosswalk/frtb-drc.yml`](../crosswalk/frtb-drc.yml)
- [`docs/regulatory/crosswalk/frtb-rrao.yml`](../crosswalk/frtb-rrao.yml)
