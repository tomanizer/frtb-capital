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
| Excluded | The behavior belongs outside `frtb-sbm`, usually in upstream systems or suite orchestration. |
| Unsupported | The package must fail explicitly until the profile or feature has cited rules and deterministic tests. |
| Out of scope | Deliberately deferred beyond the current phase boundary. |

## Phase-1 support status (GIRR delta vertical slice)

Parent issue: [#151](https://github.com/tomanizer/frtb-capital/issues/151).

| Area | Phase-1 status | Notes |
| --- | --- | --- |
| Package scaffold and public boundary | Scaffold | `calculate_sbm_capital` fails explicitly until the public API wiring issue lands. |
| Model documentation and traceability | Planned | This documentation pack; updated as implementation PRs land. |
| Canonical data models and validation | Planned | #153 |
| Rule profile and GIRR delta reference data | Planned | #154 |
| Weighted sensitivities (GIRR delta) | Planned | #155 |
| Intra-bucket aggregation | Planned | #156 |
| Inter-bucket aggregation and scenario selection | Planned | #157 |
| Public GIRR delta capital API | Planned | #158 |
| Audit/replay and synthetic fixtures | Planned | #159 |
| Vega capital | Unsupported | Explicit fail-closed until cited contracts and fixtures exist. |
| Curvature capital | Unsupported | Explicit fail-closed until cited contracts and fixtures exist. |
| CSR, equity, commodity, FX risk classes | Unsupported | Explicit fail-closed until cited mappings and fixtures exist. |
| CRIF/CSV adapters | Out of scope | Phase 1 uses synthetic canonical fixtures only. |
| SA composition | Excluded | Belongs in `frtb-orchestration`. |
| Analytical Euler attribution | Out of scope | Stable ids and branch metadata preserved for future work. |

No document or test in this package should describe outputs as final regulatory
capital. U.S. NPR 2.0 material is proposed-rule comparison only.

## Source register

| Source family | Primary references used by this package | Package status |
| --- | --- | --- |
| Basel Standardised Approach | Basel Framework MAR20 and MAR21. MAR20.4 places SBM in the SA stack. MAR21.1-MAR21.101 define risk classes, measures, weights, buckets, and aggregation. | Planned for phase-1 GIRR delta slice. |
| U.S. NPR 2.0 | Federal Register 91 FR 14952, March 27, 2026. Section V.A.7.a and pages around 91 FR 15037 define the six-step standardized non-default process. | Planned comparison profile for phase 1; proposed-rule material only. |
| EU CRR3 | Regulation (EU) 2024/1623 Articles 325e-325az. | Planned comparison profile; not in phase-1 GIRR delta slice. |
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

## Code to regulation (planned module map)

| Module | Responsibility | Basel reference | U.S. NPR 2.0 reference | Current boundary |
| --- | --- | --- | --- | --- |
| `scaffold.py` | Public calculation boundary, package metadata, and scaffold failure path. | MAR20.4 SA component context. | Section V.A.7.a package-scope context. | Scaffold until public API wiring lands. |
| `_version.py` | Package code-version identity for audit records. | MAR21 calculation traceability context. | Section V.A.7.a step traceability context. | Implemented for package identity only. |
| `__init__.py` | Stable package export boundary. | MAR20.4 SA component context. | Section V.A.7.a package-scope context. | Scaffold narrow public surface. |
| `data_models.py` | Frozen sensitivity, context, weighted sensitivity, bucket, risk-class, and result dataclasses. | MAR21.1-MAR21.8. | Section V.A.7.a steps one through three. | Planned (#153). |
| `validation.py` | Input invariants, duplicate identity checks, lineage checks, and explicit package input errors. | MAR21 risk-factor assignment context. | Section V.A.7.a steps one and two. | Planned (#153). |
| `regimes.py` | Rule-profile identity, support declarations, unsupported-profile guardrails, and deterministic profile hash. | MAR21 profile for Basel SBM mechanics. | Section V.A.7.a U.S. profile. | Planned (#154). |
| `reference_data.py` | GIRR bucket definitions, tenor sets, risk weights, correlations, scenario labels, and citation ids. | MAR21 GIRR tables. | Section V.A.7.a risk-weight and correlation steps. | Planned (#154). |
| `weighted_sensitivity.py` | Cited risk-weight lookup and weighted sensitivity records for supported measures. | MAR21 risk-weight provisions. | Section V.A.7.a step three. | Planned (#155). |
| `aggregation.py` | Shared intra-bucket and inter-bucket aggregation, scenario evaluation, and floors. | MAR21 aggregation formulas. | Section V.A.7.a steps four through six. | Planned (#156, #157). |
| `capital.py` | Public calculation entry point wiring validation, profiles, weighting, aggregation, and result assembly. | MAR21 end-to-end SBM mechanics. | Section V.A.7.a full process. | Planned (#158). |
| `audit.py` | Result serialization, input/profile hashes, and reconciliation checks. | MAR21 component traceability by formula. | Section V.A.7.a audit context. | Planned (#159). |
| `crif.py` | Optional CRIF-to-canonical mapping with lineage and rejected rows. | MAR21 risk-type mapping context only. | Section V.A.7.a canonical field mapping context. | Out of scope for phase 1. |

## Cross-links

| Document | Location |
| --- | --- |
| Module planning pack | [`docs/modules/frtb-sbm/README.md`](../../../docs/modules/frtb-sbm/README.md) |
| Requirements registry | [`docs/modules/frtb-sbm/requirements/BASEL_FRTB_SBM.yml`](../../../docs/modules/frtb-sbm/requirements/BASEL_FRTB_SBM.yml) |
| Regulatory assumptions | [`REGULATORY_ASSUMPTIONS.md`](REGULATORY_ASSUMPTIONS.md) |
| Package README | [`../README.md`](../README.md) |
| Issue breakdown | [`docs/modules/frtb-sbm/ISSUE_BREAKDOWN.md`](../../../docs/modules/frtb-sbm/ISSUE_BREAKDOWN.md) |
