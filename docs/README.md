# Documentation

This directory is the suite-level documentation home for `frtb-capital`.
Package-local evidence remains beside the package that owns the executable
model.

## Primary Navigation

| Area | Purpose |
| --- | --- |
| [Architecture](ARCHITECTURE.md) | Workspace structure, package boundaries, dependency rules, and orchestration ownership. |
| [Modules](modules/README.md) | Component documentation for implemented and partial-runtime capital modules. |
| [ADRs](decisions/) | Architecture and material model decisions. |
| [Documentation ownership](DOCUMENTATION_OWNERSHIP.md) | Canonical sources, review ownership, status vocabulary, and stale-roadmap policy. |
| [Validation packs](VALIDATION_PACK.md) | Suite index for validation evidence and package review bundles. |
| [Regulatory corpus](regulatory/README.md) | Source register, jurisdictional profiles, and component regulatory crosswalks. |
| [Quality](quality/) | Coverage, mutation-testing, and engineering-quality evidence. |
| [Performance](performance/) | Benchmark baselines and target-scale evidence. |
| [Release process](RELEASE_PROCESS.md) | Versioning, approval, tagging, and release-note policy. |
| [Agent worktrees](AGENT_WORKTREE_POLICY.md) | Protected-main and per-agent worktree workflow. |

## Documentation Boundaries

- `docs/modules/<component>/` holds suite-level model, product, regulatory, and
  planning documentation for each capital component.
- `packages/<component>/docs/` holds package-local evidence needed by code,
  tests, notebooks, and implementation review.
- `SA` is a regulatory composition label, not a package. The Standardised
  Approach total is composed from `frtb-sbm`, `frtb-drc`, and `frtb-rrao`.
- IMA is one package with internal calculation components. RFET, PLA,
  backtesting, stress-period selection, expected shortfall, SES, and capital
  assembly are documented as internal components under
  [modules/frtb-ima/components/](modules/frtb-ima/components/).
