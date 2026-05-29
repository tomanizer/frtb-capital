# frtb-rrao model documentation

## Purpose

This page is the front door for RRAO implementation documentation. It separates
regulatory source mapping, product requirements, architecture, issue sequencing,
and package-local traceability so future implementation PRs have one place to
update reviewer-facing status.

`frtb-rrao` now has a partial implementation. The package import boundary,
canonical validation, classification, line add-ons, public calculation API, and
deterministic audit result serialization are implemented for supported Basel
MAR23, U.S. NPR 2.0, and EU CRR3 comparison-profile canonical inputs.

## Documentation map

| Document | Scope | Status |
| --- | --- | --- |
| [Product requirements](PRD.md) | Product boundary, users, non-goals, delivery slices, and acceptance criteria. | Planned implementation scope. |
| [Regulatory requirements](REGULATORY_REQUIREMENTS.md) | Human-readable RRAO requirements with source citations. | Planned v1 source map. |
| [Detailed requirements](DETAILED_REQUIREMENTS.md) | Functional, non-functional, audit, and adapter requirements. | Planned v1 source map. |
| [Architecture and data design](ARCHITECTURE_AND_DATA_DESIGN.md) | Proposed modules, calculation flow, enums, dataclasses, invariants, and test layout. | Planned implementation design. |
| [Decisions and implementation plan](DECISIONS_AND_PLAN.md) | Design decisions, sequencing, risk assessment, and open questions. | Planned implementation design. |
| [Workable issue breakdown](ISSUE_BREAKDOWN.md) | PR-sized implementation issues for the `frtb-rrao v1` milestone. | Issue-backed delivery plan. |
| [Requirements registry](requirements/BASEL_FRTB_RRAO.yml) | Machine-checkable requirements and target modules/tests. | Planned and partial statuses. |
| [Package regulatory traceability](../../../packages/frtb-rrao/docs/REGULATORY_TRACEABILITY.md) | Package-local code-to-regulation and regulation-to-code cross-reference. | Scaffold plus planned modules. |
| [Package regulatory assumptions](../../../packages/frtb-rrao/docs/REGULATORY_ASSUMPTIONS.md) | Source-cited boundaries for classification, notional treatment, add-ons, exclusions, and jurisdiction support. | Scaffold plus planned v1 basis. |
| [Package regulatory sources](../../../packages/frtb-rrao/docs/regulatory_sources.yml) | Link-only source manifest for official references and implementation references. | Partial source-control asset. |

## Status summary

| Area | Status | Next issue |
| --- | --- | --- |
| Public package boundary | Partial | Issue #87 added `calculate_rrao_capital` for supported canonical inputs; unsupported profiles and evidence paths still fail closed. |
| Regulatory source pack | Partial | Issue #81 creates the package-local traceability skeleton. |
| Canonical data models and validation | Implemented | Issue #82 added frozen public models and deterministic input validation. |
| Rule profiles and reference data | Implemented | Issue #83 added cited Basel MAR23 and U.S. NPR 2.0 lookup tables; issue #91 added the EU CRR3 comparison profile. |
| Classification and exclusions | Partial | Issue #85 added cited classification decisions and exclusion decisions; exact match-group validation remains future work. |
| Line add-ons and subtotals | Implemented | Issue #86 added additive line add-ons and deterministic explain subtotals. |
| Public API and audit records | Implemented | Issue #87 added public result assembly, input/profile hashes, deterministic serialization, and reconciliation checks. |
| Synthetic validation fixture | Implemented | Issue #88 added the `tests/fixtures/rrao_v1/` pack, expected outputs, invalid cases, loader, and replay tests. |
| Optional adapters | Implemented | Issue #89 added the standard-library CRIF/FNet adapter with lineage, warnings, and rejected-row audit records. |
| Investment fund inclusion | Implemented | Issue #90 added a U.S. NPR 2.0 `__.205(e)(3)(iii)` backstop-method descriptor and cited `__.211(a)(3)` classification path. |
| EU comparison profile | Implemented | Issue #91 added Article 325u and Delegated Regulation (EU) 2022/2328 mappings with EU fixture coverage. |
| Orchestration SA composition | Partial outside package | Issue #92 added an orchestration-side RRAO result handoff while SA aggregation still fails until SBM and DRC outputs are compatible. |
| Performance and replay controls | Implemented | Issue #93 added the `make rrao-benchmark` target, deterministic replay hashes, and target-scale runtime documentation. |

## Review checklist

Before treating any RRAO change as implementation-ready, verify:

1. Every capital behavior cites Basel MAR23, U.S. proposed section `__.211`, or
   a mapped EU article/annex entry.
2. The package still fails closed for unsupported profiles and ambiguous
   classification evidence.
3. Exclusions appear as cited zero-capital records, not as dropped rows.
4. Public GitHub references are used only for adapter shape or explain-output
   inspiration.
5. New runtime code stays within package boundaries and does not import sibling
   capital packages.
