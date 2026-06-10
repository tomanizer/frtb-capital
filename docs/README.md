# Documentation

This directory is the suite-level documentation home for `frtb-capital`.
Package-local evidence remains beside the package that owns the executable
model.

## Start Here for Users

| Need | Start with | Then run or read |
| --- | --- | --- |
| Understand the upstream data contract | [Client integration guide](CLIENT_INTEGRATION.md) | `make demo`, then the relevant package guide below. |
| See all package demos execute from the repo root | Root [`README.md`](../README.md#local-development) | `make demo` or `make examples-check`. |
| Review notebook teaching and validation material | Package notebook READMEs | `make notebooks-check` for the current smoke-tested notebook set. |
| Wire component outputs into SA or top-of-house suite capital | [Orchestration module](modules/frtb-orchestration/README.md) | [orchestration module guide](modules/frtb-orchestration/README.md). |
| Persist capital results and attribution records | [Result-store module](modules/frtb-result-store/README.md) | [frtb-result-store README](../packages/frtb-result-store/README.md). |

## Package Guides

| Package | Guide | Demo |
| --- | --- | --- |
| IMA | [docs/modules/frtb-ima/CLIENT_DELIVERY.md](modules/frtb-ima/CLIENT_DELIVERY.md) | `uv run python packages/frtb-ima/examples/run_demo.py` |
| SBM | [packages/frtb-sbm/docs/PACKAGE_JOURNEY.md](../packages/frtb-sbm/docs/PACKAGE_JOURNEY.md) | `uv run python packages/frtb-sbm/examples/run_demo.py` |
| DRC | [packages/frtb-drc/docs/PACKAGE_JOURNEY.md](../packages/frtb-drc/docs/PACKAGE_JOURNEY.md) | `uv run python packages/frtb-drc/examples/run_demo.py` |
| RRAO | [packages/frtb-rrao/docs/PACKAGE_JOURNEY.md](../packages/frtb-rrao/docs/PACKAGE_JOURNEY.md) | `uv run python packages/frtb-rrao/examples/run_demo.py` |
| CVA | [packages/frtb-cva/docs/PACKAGE_JOURNEY.md](../packages/frtb-cva/docs/PACKAGE_JOURNEY.md) | `uv run python packages/frtb-cva/examples/run_demo.py` |
| Orchestration | [docs/modules/frtb-orchestration/README.md](modules/frtb-orchestration/README.md) | `uv run python packages/frtb-orchestration/examples/run_demo.py` |

## Primary Navigation

| Area | Purpose |
| --- | --- |
| [Architecture](ARCHITECTURE.md) | Workspace structure, package boundaries, dependency rules, and orchestration ownership. |
| [Capital attribution methods](CAPITAL_ATTRIBUTION_METHODS.md) | Suite-level guide to Euler attribution, residuals, unsupported branches, standalone contribution, and finite-difference impact. |
| [Attribution implementation matrix](ATTRIBUTION_IMPLEMENTATION_MATRIX.md) | Package-by-package attribution support, grains, public helpers, unsupported branches, and test evidence. |
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
