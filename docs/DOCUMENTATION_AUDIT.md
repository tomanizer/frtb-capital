# Documentation Audit

Date: 2026-05-28

## Scope

This audit checks whether repository documentation reflects the current
`frtb-capital` monorepo after the migration from the historical
`tomanizer/FRTB-IMA` repository.

## Current Structure

- Root repository: `tomanizer/frtb-capital`
- Implemented package: `packages/frtb-ima`
- Shared package: `packages/frtb-common`
- Standardised Approach component packages: `packages/frtb-sbm`,
  `packages/frtb-drc`, and `packages/frtb-rrao`
- CVA package: `packages/frtb-cva`
- Suite orchestration package: `packages/frtb-orchestration`
- Root CI: `.github/workflows/ci.yml`
- Package-local IMA docs: `packages/frtb-ima/docs/`
- Suite-level ADRs: `docs/decisions/`
- Suite-level module documentation home: `docs/modules/`
- IMA model documentation pack:
  `docs/modules/frtb-ima/model_documentation/`

## Findings Addressed

- Replaced standalone IMA repository language with package-in-monorepo language.
- Updated SBM, DRC, RRAO, and CVA references from separate repositories to
  sibling workspace packages.
- Pointed root documentation navigation at the current IMA regulatory docs
  instead of non-existent root regulatory docs.
- Clarified that `frtb-common`, SBM, DRC, RRAO, CVA, and orchestration are
  workspace packages rather than missing directories. Their implementation
  status is now maintained in `docs/quality/package_maturity.toml` and
  `docs/quality/PACKAGE_STATUS.md`.
- Added the missing `packages/frtb-ima/CHANGELOG.md` placeholder required by
  package versioning guidance.
- Added a suite-level `docs/modules/` home for module documentation and moved
  the IMA model pack under `docs/modules/frtb-ima/model_documentation/`.
- Corrected security documentation that previously claimed configured
  Dependabot and vulnerability scans before audit-followup work implements
  them.

## Residual Follow-Ups

- Future package work: add formal model documentation packs as scaffolded
  components become implemented calculation packages.
- `tomanizer/frtb-capital#2`: dependency pinning and supply-chain hygiene.
- `tomanizer/frtb-capital#3`: governance file completion, including PR
  templates if desired.
- `tomanizer/frtb-capital#8`: regulatory thresholds and citations in policy
  configuration.

This audit did not change calculation code.
