# RRAO regulatory traceability

## Purpose

This document maps `frtb-rrao` package code and planned code to the regulatory
paragraphs that motivate it. It is a traceability aid for implementation and
review; it is not legal advice and it does not make scaffolded or planned
features capital-producing.

The companion source manifest is
[`docs/regulatory_sources.yml`](regulatory_sources.yml). It keeps official URLs,
section hints, status labels, and implementation-reference links without
vendoring regulatory text into the package.

Use this document in two directions:

- **Code to regulation:** start from an existing or planned module and inspect
  the cited Basel, U.S. NPR, and EU anchors.
- **Regulation to code:** start from a regulatory topic and inspect whether the
  package implements, plans, excludes, or rejects that scope.

## Status taxonomy

| Status | Meaning in `frtb-rrao` |
| --- | --- |
| Scaffold | The package has an importable boundary and explicit failure path, but does not calculate RRAO capital. |
| Planned | The behavior is issue-backed and source-mapped, but no capital-producing code exists yet. |
| Partial | Some documentation, data contract, or helper exists, but the end-to-end behavior is not complete. |
| Implemented | Tested code produces the cited behavior for supported inputs. |
| Excluded | The behavior belongs outside `frtb-rrao`, usually in upstream systems or suite orchestration. |
| Unsupported | The package must fail explicitly until the profile or feature has cited rules and deterministic tests. |

## Source register

| Source family | Primary references used by this package | Package status |
| --- | --- | --- |
| Basel Standardised Approach | Basel Framework MAR20 and MAR23. MAR20.4 places RRAO in the Standardised Approach stack. MAR23.1-MAR23.8 define residual-risk scope, exclusions, back-to-back treatment, and the 1.0% / 0.1% add-on mechanics. | Planned v1 basis. |
| U.S. NPR 2.0 | Federal Register 91 FR 14952, March 27, 2026. Section V.A.7.b and proposed section `__.211` define proposed U.S. residual-risk coverage, exclusions, gross effective notional, and add-on percentages. | Planned v1 profile; proposed-rule material only. |
| EU CRR / CRR3 | Regulation (EU) No 575/2013 Article 325u and Commission Delegated Regulation (EU) 2022/2328 Articles 1-3 and Annex. | Comparison profile planned; capital calculation unsupported until mapped and fixture-tested. |
| EBA RTS background | EBA residual risk add-on RTS page. | Background only; not an independent calculation source. |
| Public implementation references | `frtb-net/FRTB` `SA_RRAO_Calc.py` and FNet format documentation. | Adapter and explain-shape inspiration only; not regulatory sources. |

Use `docs/regulatory_sources.yml` for topic-level links and review notes.

## Primary-source links

- Basel Framework MAR20, Standardised approach:
  https://www.bis.org/basel_framework/chapter/MAR/20.htm
- Basel Framework MAR23, Residual risk add-on:
  https://www.bis.org/basel_framework/chapter/MAR/23.htm
- U.S. NPR 2.0 / Federal Register 91 FR 14952:
  https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959
- OCC PDF copy of 91 FR 14952:
  https://www.occ.gov/news-issuances/federal-register/2026/91fr14952.pdf
- Regulation (EU) No 575/2013 consolidated text, Article 325u:
  https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02013R0575-20240709
- Commission Delegated Regulation (EU) 2022/2328:
  https://eur-lex.europa.eu/eli/reg_del/2022/2328/oj/eng
- EBA RTS on residual risk add-on:
  https://www.eba.europa.eu/legacy/regulation-and-policy/regulatory-activities/market-counterparty-and-cva-risk/regulatory-2?version=2021

## Code to regulation

| Module or planned module | Responsibility | Basel reference | U.S. NPR 2.0 reference | EU reference | Current boundary |
| --- | --- | --- | --- | --- | --- |
| `scaffold.py` | Public calculation boundary and package metadata while RRAO capital is not implemented. | MAR20.4 SA component context; MAR23.1 RRAO scope. | Section V.A.7.b and proposed section `__.211` scope. | Article 325u comparison scope. | Scaffold: `calculate_rrao_capital` raises `NotImplementedCapitalComponentError`. |
| `_version.py` | Package code-version identity for future audit records. | MAR23 calculation traceability context. | Proposed section `__.211(c)` line-capital traceability context. | Article 325u comparison context. | Implemented for package identity only; no model approval status. |
| `__init__.py` | Stable package export boundary. | MAR20.4 SA component context. | Section V.A.7.b package-scope context. | Article 325u comparison context. | Scaffold export of metadata and explicit failure entry point. |
| `data_models.py` | Frozen input, context, classification, capital-line, subtotal, result, citation, and lineage dataclasses. | MAR23.1-MAR23.8. | Proposed section `__.211(a)`-`__.211(c)`. | Article 325u; Delegated Regulation 2022/2328 Articles 1-3 and Annex. | Implemented as public data contracts; no classification or capital logic. |
| `validation.py` | Input invariants, gross effective notional checks, duplicate identity checks, lineage checks, and explicit package input errors. | MAR23.8 gross notional mechanics. | Proposed section `__.211(c)(2)` gross effective notional. | Article 325u comparison only. | Implemented for canonical input validation; rule-profile lookup remains planned. |
| `regimes.py` | Rule-profile identity, support declarations, profile status, unsupported-profile guardrails, and deterministic profile hash. | MAR23 profile for Basel RRAO mechanics. | Proposed section `__.211` U.S. profile. | Article 325u and Delegated Regulation 2022/2328 EU profile. | Implemented for Basel MAR23 and U.S. NPR 2.0 profile lookup; EU/PRA fail closed. |
| `reference_data.py` | Risk weights, evidence categories, exclusion reason tables, and citation ids. | MAR23.2-MAR23.8. | Proposed section `__.211(a)`-`__.211(c)`. | Delegated Regulation 2022/2328 Articles 1-3 and Annex. | Implemented cited lookup tables for Basel MAR23 and U.S. NPR 2.0; EU table remains unsupported. |
| `classification.py` | Cited classification and exclusion decisions for canonical positions. | MAR23.2-MAR23.7. | Proposed section `__.211(a)`-`__.211(b)`. | Delegated Regulation 2022/2328 Articles 1-3 and Annex. | Planned in issue #85. |
| `capital.py` | Additive line add-ons, zero-capital excluded lines, deterministic subtotals, and total RRAO. | MAR23.8. | Proposed section `__.211(c)`. | Article 325u comparison mechanics once mapped. | Planned in issue #86 and public API in issue #87. |
| `audit.py` | Result serialization, input/profile hashes, line reconciliation, and additive contribution reporting. | MAR23 calculation auditability context. | Proposed section `__.211(c)` line add-ons and reporting notional source. | Article 325u comparison context. | Planned in issues #87 and #94. |
| `crif.py` | Optional CRIF/FNet-shaped adapter into canonical `RraoPosition` records. | MAR23 risk-type mapping context only. | Proposed section `__.211` canonical field mapping context. | Article 325u comparison mapping context. | Planned in issue #89; adapter only, not a calculation kernel. |
| `fixtures.py` | Synthetic examples for source-cited classification, exclusions, and deterministic replay. | MAR23.2-MAR23.8. | Proposed section `__.211(a)`-`__.211(c)`. | Delegated Regulation 2022/2328 Articles 1-3 and Annex for EU fixtures. | Planned in issue #88. |

## Regulation to code

| Regulatory topic | Basel anchor | U.S. NPR 2.0 anchor | EU anchor | Package entry points | Coverage status |
| --- | --- | --- | --- | --- | --- |
| SA composition includes RRAO | MAR20.4. | Section V.A.7.b standardized approach context. | Article 325u standardized approach context. | `scaffold.py`; future orchestration handoff. | Package boundary planned; SA total excluded from `frtb-rrao` and owned by orchestration. |
| Exotic residual-risk coverage | MAR23.2 and MAR23.8(2)(a). | Section V.A.7.b.i and proposed section `__.211(a)(1)`, `__.211(c)(1)(i)`. | Delegated Regulation 2022/2328 Article 1. | Planned `classification.py`, `reference_data.py`, `capital.py`. | Planned for U.S./Basel v1; EU capital unsupported until mapped. |
| Other residual-risk coverage | MAR23.3 and MAR23.8(2)(b). | Section V.A.7.b.i and proposed section `__.211(a)(2)`, `__.211(c)(1)(ii)`. | Delegated Regulation 2022/2328 Articles 2-3 and Annex. | Planned `classification.py`, `reference_data.py`, `capital.py`. | Planned for U.S./Basel v1; EU profile planned separately. |
| Investment fund inclusion | MAR23 residual-risk scope context. | Proposed section `__.211(a)(3)`. | Article 325u comparison context. | Planned `classification.py` and fixtures. | Unsupported until issue #90 adds a cited input contract. |
| Supervisor-directed inclusion | MAR23 residual-risk scope context. | Proposed section `__.211(a)(4)`. | No v1 EU mapping. | Planned `classification.py`. | Planned for U.S. profile; requires directive evidence id. |
| Exclusions | MAR23.4-MAR23.7. | Proposed section `__.211(b)`. | Delegated Regulation 2022/2328 Article 3 comparison context. | Planned `classification.py` and zero-capital result lines. | Planned for U.S./Basel v1. |
| Gross effective notional and risk weights | MAR23.8. | Proposed section `__.211(c)(1)`-`__.211(c)(2)`. | Article 325u comparison context. | Planned `validation.py`, `reference_data.py`, `capital.py`. | Planned for U.S./Basel v1. |
| Public GitHub adapter shapes | Not a regulatory source. | Not a regulatory source. | Not a regulatory source. | Planned `crif.py`. | Optional adapter inspiration only; never overrides cited classification evidence. |

## Module docstring convention

Every future capital or classification module should include a short
`Regulatory traceability` block naming:

1. the Basel anchor,
2. the U.S. NPR 2.0 anchor,
3. the EU/CRR anchor if the module touches an EU comparison profile,
4. the row in this document that reviewers should inspect.

Do not paste regulatory text into module docstrings. Keep docstrings short and
route reviewers here for the full cross-reference.

## Maintenance rules

When adding or changing RRAO behavior:

1. Update the **Code to regulation** table.
2. Update the **Regulation to code** table when a new regulatory topic is
   implemented, excluded, or explicitly unsupported.
3. Update [`REGULATORY_ASSUMPTIONS.md`](REGULATORY_ASSUMPTIONS.md) for any
   implementation decision that affects classification, exclusion, notional
   treatment, or profile support.
4. Update [`docs/regulatory_sources.yml`](regulatory_sources.yml) when a new
   source family, implementation reference, or source hint is introduced.
5. Keep U.S. NPR 2.0 content labelled as proposed-rule material and do not
   present package outputs as final regulatory capital.
