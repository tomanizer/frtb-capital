# Documentation Audit

Date: 2026-06-03

## Scope

This audit checks whether repository documentation reflects the current
`frtb-capital` monorepo structure, package maturity, and public integration
surfaces. It supersedes the 2026-05-28 migration audit, which addressed the
historical `tomanizer/FRTB-IMA` repository move.

## Current structure

| Package | Maturity | Primary doc home |
| --- | --- | --- |
| `frtb-common` | `shared` | `packages/frtb-common/README.md`, `docs/modules/frtb-common/` |
| `frtb-ima` | `implemented` | `packages/frtb-ima/`, `docs/modules/frtb-ima/` |
| `frtb-sbm` | `partial_runtime` | `packages/frtb-sbm/`, `docs/modules/frtb-sbm/` |
| `frtb-drc` | `partial_runtime` | `packages/frtb-drc/`, `docs/modules/frtb-drc/` |
| `frtb-rrao` | `implemented` | `packages/frtb-rrao/`, `docs/modules/frtb-rrao/` |
| `frtb-cva` | `partial_runtime` | `packages/frtb-cva/`, `docs/modules/frtb-cva/` |
| `frtb-orchestration` | `orchestration_implemented` | `docs/modules/frtb-orchestration/` (canonical), `packages/frtb-orchestration/README.md` |
| `frtb-result-store` | `result_store_partial` | `packages/frtb-result-store/`, `docs/modules/frtb-result-store/` |

Authoritative implementation status: [`docs/quality/package_maturity.toml`](quality/package_maturity.toml)
and the generated [`docs/quality/PACKAGE_STATUS.md`](quality/PACKAGE_STATUS.md).

## Findings addressed (2026-06-03)

- Aligned `packages/frtb-orchestration/README.md`, `AGENTS.md`, and `CLAUDE.md`
  with implemented `calculate_suite_capital` and module documentation.
- Added [ADR 0039](decisions/0039-orchestration-suite-capital-aggregation.md) and
  updated ADR 0018 / ADR 0032 cross-references for suite aggregation.
- Refreshed `docs/ARCHITECTURE.md` SBM and orchestration status sections.
- Removed stale “scaffolded sibling packages” language from IMA agent and
  regulatory assumption docs.
- Expanded `packages/frtb-drc/README.md` and added `docs/modules/frtb-ima/PUBLIC_API.md`.
- Synced `docs/modules/frtb-rrao/PUBLIC_API.md` with PRA_UK_CRR and
  `to_component_summary`.
- Added `packages/frtb-result-store/CLAUDE.md` and updated root `CLAUDE.md`
  workspace structure.
- Corrected the SBM summary line in `docs/modules/README.md`.

## Residual follow-ups

- Promote a suite-level audit-record home from `frtb_ima.audit` when an ADR
  extracts shared audit types into `frtb-common`.
- Add `docs/modules/frtb-orchestration/PUBLIC_API.md` if orchestration exports
  grow beyond summary-handoff symbols.
- Keep model-documentation packs aligned when partial-runtime packages add new
  cited paths (see [`docs/modules/MODEL_DOCUMENTATION_PROMOTION_PLAN.md`](modules/MODEL_DOCUMENTATION_PROMOTION_PLAN.md)).
- Manifest-driven end-to-end suite runs from a single `CapitalRunManifest` may
  need additional client examples beyond component summary handoffs.

This audit did not change calculation code.