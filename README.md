# frtb-capital

**Suite of FRTB market-risk capital calculation components.**

> ⚠️ Prototype workspace. Not for regulatory reporting. Each component is a separate model under SR 11-7 / PRA SS 1/23 and requires independent validation before production use.

## Components

This repository is a `uv` workspace intended to contain one Python package per
capital component plus a shared common package. The migrated IMA package is the
only implemented capital package today; the other packages are planned sibling
packages tracked by the audit backlog.

| Package | Purpose | Status |
|---|---|---|
| `packages/frtb-common` | Shared primitives: sign conventions, scenario metadata, audit records, regulatory policy base, business calendar | Planned |
| `packages/frtb-ima` | Internal Models Approach capital for model-eligible trading desks | Migrated from `tomanizer/FRTB-IMA` |
| `packages/frtb-sa` | Standardized Approach for market risk | Planned |
| `packages/frtb-drc` | Default Risk Charge | Planned |
| `packages/frtb-cva` | Credit Valuation Adjustment capital | Planned |
| `packages/frtb-orchestration` | Suite-level capital aggregation and firm-level consolidation | Planned |

## Why a monorepo

One repository preserves consistent style, shared abstractions, and atomic cross-cutting regulatory changes across the four capital charges. Each package is independently versioned with its own model documentation pack, so SR 11-7 / PRA SS 1/23 model boundaries remain clean.

For the architectural rationale, see [`docs/decisions/0002-monorepo-structure.md`](docs/decisions/0002-monorepo-structure.md).

## Install

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

This installs every implemented workspace package in editable mode plus dev
dependencies.

## Local development

```bash
make check          # lint + typecheck + tests across the workspace
make ima            # work on the IMA package only
make integration    # cross-package integration tests (when orchestration lands)
```

Per-package targets are available from each package's own `Makefile` or via `uv run`.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — suite architecture and dependency graph
- [`packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md`](packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md) — IMA code ↔ regulation cross-reference
- [`packages/frtb-ima/docs/REGULATORY_ASSUMPTIONS.md`](packages/frtb-ima/docs/REGULATORY_ASSUMPTIONS.md) — IMA modelling boundaries and proposed-rule basis
- [`docs/decisions/`](docs/decisions/) — architectural decision records (ADRs)
- [`docs/model_documentation/`](docs/model_documentation/) — per-model documentation packs

## Governance

- [`CHANGELOG.md`](CHANGELOG.md) — suite-level release notes (per-package CHANGELOGs in each package)
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to contribute, material-change policy
- [`SECURITY.md`](SECURITY.md) — vulnerability reporting

## What this suite is not

- A production regulatory calculator.
- A complete implementation of any final-rule FRTB regime.
- A substitute for independent model validation, legal review, or supervisory approval.
