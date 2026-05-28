# Changelog

All notable suite-level changes will be documented here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Per-package change history lives under each package (e.g. `packages/frtb-ima/CHANGELOG.md`).

## [Unreleased]

### Added

- Initial `frtb-capital` monorepo skeleton with `uv` workspace.
- `packages/frtb-ima/` migrated from `tomanizer/FRTB-IMA` with full git history preserved.
- Suite-level governance files: `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`.
- Suite-level architecture documentation under `docs/`.
- Initial ADRs documenting the monorepo decision and the SA/DRC/CVA scope boundary.
- Supply-chain hygiene with minor-capped dev dependencies, weekly Dependabot
  monitoring, a `pip-audit` CI job, and CycloneDX SBOM generation under
  `dist/sbom/`.

### Notes

- This is the initial workspace bootstrap. No regulatory calculation logic has changed; the IMA package is functionally identical to its standalone state at `tomanizer/FRTB-IMA` commit `7f704e7`.
