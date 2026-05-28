# Changelog

All notable suite-level changes will be documented here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Per-package change history lives under each package (e.g. `packages/frtb-ima/CHANGELOG.md`).

## [Unreleased]

### Added

- Weekly/manual mutation-testing workflow and root `make mutation` target for
  the FRTB-IMA calculation-module baseline.
- Per-module IMA coverage gate with a documented 90% interim floor and CI
  enforcement through `make test`.
- Independent IMA numerical reference-vector tests for ES, LHA ES, IMCC, SES,
  PLA, and supervisory multiplier mappings.
- FRTB-IMA model documentation pack scaffold covering intended use,
  conceptual soundness, derivation, assumptions and limitations, sensitivity
  analysis, monitoring, and change history.
- Material-change policy and backfilled ADRs for major FRTB-IMA model-design
  decisions, with a PR template reminder for ADR review.
- Scheduled/manual FRTB-IMA target-scale benchmark workflow with `make benchmark`
  and a checked-in performance-baseline directory.
- Governance completion for audit issue #3: documented release approvals,
  versioning, tagging, and material-change handling in
  `docs/RELEASE_PROCESS.md`.

## [0.1.0] - 2026-05-28

### Added

- Initial `frtb-capital` monorepo skeleton with `uv` workspace.
- `packages/frtb-ima/` migrated from `tomanizer/FRTB-IMA` with full git history preserved.
- Suite-level governance files: `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`.
- Suite-level architecture documentation under `docs/`.
- Initial ADRs documenting the monorepo decision and the SA/DRC/CVA scope boundary.
- Documentation alignment for the monorepo migration, including root and
  package agent guidance, model-documentation index, documentation audit, and
  package changelog updates.
- Supply-chain hygiene (PR #24) with minor-capped dev dependencies, weekly
  Dependabot monitoring, a `pip-audit` CI job, and CycloneDX SBOM generation
  under `dist/sbom/`.

### Fixed

- CI uses Makefile targets consistently for workspace-scoped lint, typecheck,
  tests, examples, notebooks, dependency audit, and SBOM generation.

### Notes

- This is the initial workspace bootstrap. No regulatory calculation logic has changed; the IMA package is functionally identical to its standalone state at `tomanizer/FRTB-IMA` commit `7f704e7`.
