# frtb-capital

**Suite of FRTB market-risk capital calculation components.**

> ⚠️ Prototype workspace. Not for regulatory reporting. Each component is a separate model under SR 11-7 / PRA SS 1/23 and requires independent validation before production use.

## Components

This repository is a `uv` workspace with one Python package per capital
component, a shared common package, orchestration, and result-store
infrastructure. IMA and RRAO have implemented public calculation paths, DRC has a partial
non-securitisation runtime path, SBM has delta capital implemented for five
risk classes (GIRR vega also implemented; curvature pending), and CVA has
Reduced BA-CVA and SA-CVA GIRR delta implemented.

The Standardised Approach is a composed calculation stack, not a standalone
package. Planned SA capital is `frtb-sbm + frtb-drc + frtb-rrao`; suite
orchestration will combine those components for SA totals and for IMA fallback
capital when a desk is not IMA-eligible.

| Package | Purpose | Status |
|---|---|---|
| `packages/frtb-common` | Shared primitives: status metadata, unsupported-feature errors, serialization, and regulatory citation helpers | Shared |
| `packages/frtb-ima` | Internal Models Approach capital for model-eligible trading desks | Implemented; migrated from `tomanizer/FRTB-IMA` |
| `packages/frtb-sbm` | Standardised Approach sensitivities-based method component | Partial runtime; delta implemented for GIRR, FX, Equity, Commodity, CSR non-sec; GIRR vega implemented; curvature pending |
| `packages/frtb-drc` | Standardised Approach default risk charge component | Partial runtime; supported non-securitisation path only |
| `packages/frtb-rrao` | Standardised Approach residual risk add-on component | Implemented for supported canonical-input profiles |
| `packages/frtb-cva` | Credit Valuation Adjustment capital | Partial runtime; Reduced BA-CVA and SA-CVA GIRR delta implemented; other SA-CVA risk classes and full hedge recognition unsupported |
| `packages/frtb-orchestration` | Suite-level capital aggregation and firm-level consolidation | Partial; component handoff contracts exist, aggregation not implemented |
| `packages/frtb-result-store` | DuckDB/Parquet store for immutable FRTB runs, drilldown, artifacts, lineage, and attribution | Partial result-store backend; not a capital calculation package |

## Why a monorepo

One repository preserves consistent style, shared abstractions, and atomic cross-cutting regulatory changes across the capital components. Each package is independently versioned with its own model documentation pack, so SR 11-7 / PRA SS 1/23 model boundaries remain clean.

For the architectural rationale, see [`docs/decisions/0002-monorepo-structure.md`](docs/decisions/0002-monorepo-structure.md).

## Install

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

This installs the full workspace in editable mode plus dev dependencies.

## Integrating

Client risk engines should use the Arrow/Parquet handoff path as the default
production ingress pattern. Start with
[`docs/CLIENT_INTEGRATION.md`](docs/CLIENT_INTEGRATION.md) for the suite-level
contract, component handoff symbols, run-context expectations, hashing, and
rejection semantics.

## Local development

```bash
make check          # lint + typecheck + coverage-gated tests across the workspace
make ima            # work on the IMA package only
make mutation       # run the focused IMA mutation-testing baseline
make mutation-rrao  # run the focused RRAO mutation-testing baseline
make mutation-score-check  # verify exported mutmut CI stats (run mutation targets first)
```

Per-package targets are available from each package's own `Makefile` or via `uv run`.

## Documentation

- [`docs/CLIENT_INTEGRATION.md`](docs/CLIENT_INTEGRATION.md) — client-facing integration guide for handoff contracts and onboarding
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — suite architecture and dependency graph
- [`docs/README.md`](docs/README.md) — documentation map
- [`docs/modules/`](docs/modules/README.md) — suite-level capital module documentation
- [`docs/modules/frtb-result-store/`](docs/modules/frtb-result-store/README.md) — result-store module documentation
- [`docs/modules/frtb-ima/`](docs/modules/frtb-ima/README.md) — FRTB-IMA module documentation front door
- [`docs/modules/standardised-approach.md`](docs/modules/standardised-approach.md) — SA composition from SBM, DRC, and RRAO
- [`docs/modules/frtb-ima/model_documentation/`](docs/modules/frtb-ima/model_documentation/README.md) — FRTB-IMA model documentation pack
- [`docs/VALIDATION_PACK.md`](docs/VALIDATION_PACK.md) — suite index for package validation bundles
- [`docs/regulatory/`](docs/regulatory/README.md) — suite-level regulatory corpus, source register, jurisdiction profiles, and component crosswalks
- [`docs/validation/challenger_models.yml`](docs/validation/challenger_models.yml) — external challenger model register for validation and reconciliation
- [`packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md`](packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md) — IMA code ↔ regulation cross-reference
- [`packages/frtb-ima/docs/REGULATORY_ASSUMPTIONS.md`](packages/frtb-ima/docs/REGULATORY_ASSUMPTIONS.md) — IMA modelling boundaries and proposed-rule basis
- [`docs/decisions/`](docs/decisions/) — architectural decision records (ADRs)
- [`docs/quality/coverage_policy.md`](docs/quality/coverage_policy.md) — implemented-package coverage floor and later production-quality target
- [`docs/quality/PACKAGE_STATUS.md`](docs/quality/PACKAGE_STATUS.md) — generated package maturity and crosswalk dashboard
- [`docs/quality/DEPENDENCY_AUDIT_AND_SBOM.md`](docs/quality/DEPENDENCY_AUDIT_AND_SBOM.md) — pip-audit and SBOM scope
- [`docs/quality/BENCHMARK_PROFILE.md`](docs/quality/BENCHMARK_PROFILE.md) — benchmark regression budgets and profiling notes
- [`docs/quality/frtb-ima/mutation_baseline.md`](docs/quality/frtb-ima/mutation_baseline.md) — IMA mutation-testing baseline and survivor review policy
- [`docs/quality/frtb-rrao/mutation_baseline.md`](docs/quality/frtb-rrao/mutation_baseline.md) — RRAO mutation-testing baseline and survivor review policy

## Governance

- [`CHANGELOG.md`](CHANGELOG.md) — suite-level release notes (per-package CHANGELOGs in each package)
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to contribute, material-change policy
- [`SECURITY.md`](SECURITY.md) — vulnerability reporting
- [`docs/RELEASE_PROCESS.md`](docs/RELEASE_PROCESS.md) — release approval, tagging, and versioning policy
- [`docs/REPO_CONTROLS.md`](docs/REPO_CONTROLS.md) — branch protection, CODEOWNERS, and release-attestation controls
- [`docs/decisions/`](docs/decisions/) — ADR log for architecture and material model decisions

## What this suite is not

- A production regulatory calculator.
- A complete implementation of any final-rule FRTB regime.
- A substitute for independent model validation, legal review, or supervisory approval.
