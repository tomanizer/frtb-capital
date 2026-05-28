# Documentation Audit

Date: 2026-05-28

## Scope

This audit checks whether repository documentation reflects the current
`frtb-capital` monorepo after the migration from the historical
`tomanizer/FRTB-IMA` repository.

## Current Structure

- Root repository: `tomanizer/frtb-capital`
- Active package: `packages/frtb-ima`
- Planned packages: `packages/frtb-common`, `packages/frtb-sbm`,
  `packages/frtb-drc`, `packages/frtb-rrao`, `packages/frtb-cva`, and
  `packages/frtb-orchestration`
- Root CI: `.github/workflows/ci.yml`
- Package-local IMA docs: `packages/frtb-ima/docs/`
- Suite-level ADRs: `docs/decisions/`
- Suite-level module documentation home: `docs/modules/`
- IMA model documentation pack:
  `docs/modules/frtb-ima/model_documentation/`

## Findings Addressed

- Replaced standalone IMA repository language with package-in-monorepo language.
- Updated SBM, DRC, RRAO, and CVA references from separate repositories to
  planned sibling packages.
- Pointed root documentation navigation at the current IMA regulatory docs
  instead of non-existent root regulatory docs.
- Clarified that `frtb-common`, SBM, DRC, RRAO, CVA, and orchestration are
  planned packages, not implemented directories.
- Added the missing `packages/frtb-ima/CHANGELOG.md` placeholder required by
  package versioning guidance.
- Added a suite-level `docs/modules/` home for module documentation and moved
  the IMA model pack under `docs/modules/frtb-ima/model_documentation/`.
- Corrected security documentation that previously claimed configured
  Dependabot and vulnerability scans before audit-followup work implements
  them.

## Residual Follow-Ups

- Future package work: add matching module documentation front doors and model
  packs as planned components become implemented packages.
- `tomanizer/frtb-capital#2`: dependency pinning and supply-chain hygiene.
- `tomanizer/frtb-capital#3`: governance file completion, including PR
  templates if desired.
- `tomanizer/frtb-capital#8`: regulatory thresholds and citations in policy
  configuration.

This audit did not change calculation code.
