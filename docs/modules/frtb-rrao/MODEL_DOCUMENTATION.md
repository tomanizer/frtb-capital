# frtb-rrao model documentation

## Purpose

This page is the front door for RRAO implementation documentation. It separates
regulatory source mapping, product requirements, architecture, issue sequencing,
and package-local traceability so future implementation PRs have one place to
update reviewer-facing status.

`frtb-rrao` is still scaffolded. The package import and explicit failure path
are implemented, but no RRAO capital result is produced yet.

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
| Public package boundary | Scaffold | Already present in `scaffold.py`; remains explicit-failure until issue #87. |
| Regulatory source pack | Partial | Issue #81 creates the package-local traceability skeleton. |
| Canonical data models and validation | Implemented | Issue #82 added frozen public models and deterministic input validation; calculation remains scaffolded. |
| Rule profiles and reference data | Implemented | Issue #83 added cited Basel MAR23 and U.S. NPR 2.0 lookup tables and unsupported EU/PRA guards. |
| Classification and exclusions | Partial | Issue #85 added cited classification decisions and exclusion decisions; exact match-group validation remains future work. |
| Line add-ons and subtotals | Planned | Issue #86. |
| Public API and audit records | Planned | Issue #87. |
| Synthetic validation fixture | Planned | Issue #88. |
| Optional adapters | Planned | Issue #89. |
| EU comparison profile | Unsupported | Issue #91 before any EU capital path may return a result. |
| Orchestration SA composition | Excluded from package | Issue #92 defines handoff after RRAO result shape is stable. |

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
