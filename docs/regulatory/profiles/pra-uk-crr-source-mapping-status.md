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
| `frtb-sbm` | `PRA_UK_CRR` | Fail-closed (`resolve_sbm_profile`) | `unsupported_fail_closed` | Source mapped to PS1/26 Appendix 1 / PRA2026/1 Articles 325c-325ay for planning; no PRA SBM runtime cell has profile-owned reference data or fixtures. |
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
| `packages/frtb-sbm/docs/regulatory_sources.yml` `uk_pra_ps1_26_sbm_asa` | `comparison_only` planning source | PS1/26 Appendix 1 / PRA2026/1 Articles 325c-325ay mapped to SBM planning topics; runtime remains fail-closed until profile-owned reference data and fixtures land. |
| `packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md` PRA rows | `unsupported_fail_closed` | All 21 PRA SBM profile/risk-class/measure cells remain runtime fail-closed. |
| `src/frtb_sbm/regimes.py` `PRA_UK_CRR` unsupported reason | `unsupported_fail_closed` | Profile resolution and capital routing remain closed until exact-cell citation ids, reference data, and fixtures land. |

## Follow-up implementation issues (not in #507 scope)

1. [#512](https://github.com/tomanizer/frtb-capital/issues/512) — IMA PRA RFET,
   NMRF, and capital-runtime enablement with `ima_pra` fixtures (delivered).
2. [#513](https://github.com/tomanizer/frtb-capital/issues/513) — RRAO PRA
   Article 325u mapping and `rrao_pra` fixtures (delivered).
3. [#1046](https://github.com/tomanizer/frtb-capital/issues/1046) — SBM PRA UK
   CRR comparison-profile expansion roadmap.
4. [#1064](https://github.com/tomanizer/frtb-capital/issues/1064) — SBM PRA
   source-map documentation and manifest update.

## Crosswalk pointers

- [`docs/regulatory/crosswalk/frtb-ima.yml`](../crosswalk/frtb-ima.yml)
- [`packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md`](../../../packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md)
- [`docs/regulatory/crosswalk/frtb-rrao.yml`](../crosswalk/frtb-rrao.yml)
