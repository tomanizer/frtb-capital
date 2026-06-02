# frtb-capital architecture

## Suite overview

`frtb-capital` is a workspace of FRTB market-risk capital calculation packages.
The structure covers IMA, the three Standardised Approach components, CVA, and
a suite-level aggregator, with a shared foundation package. Today,
`packages/frtb-ima` contains the migrated IMA implementation, `frtb-rrao`
contains an implemented canonical-input RRAO path, `frtb-drc` contains a
partial non-securitisation DRC runtime path, `frtb-sbm` has GIRR delta/vega,
FX/equity/commodity/CSR delta/vega, and row-wise curvature capital implemented
under BASEL_MAR21, and `frtb-cva` has Reduced BA-CVA and SA-CVA GIRR delta
implemented. Suite aggregation still fails explicitly until all required
component result contracts are available.

The Standardised Approach is a composed regulatory approach, not a standalone
package. In this suite, `frtb-sbm`, `frtb-drc`, and `frtb-rrao` together produce
SA capital. `frtb-orchestration` owns SA aggregation and routes non-IMA-eligible
desks to that SA component stack for fallback capital.

## Dependency graph

```
                         ┌────────────────────────┐
                         │   frtb-orchestration   │
                         │ aggregation + fallback │
                         └───────────┬────────────┘
                                     │
       ┌─────────────┬───────────────┼───────────────┬─────────────┐
       ▼             ▼               ▼               ▼             ▼
   ┌────────┐   ┌──────────┐    ┌──────────┐    ┌──────────┐  ┌────────┐
   │ frtb-  │   │ frtb-    │    │ frtb-    │    │ frtb-    │  │ frtb-  │
   │  ima   │   │  sbm     │    │  drc     │    │  rrao    │  │  cva   │
   └───┬────┘   └────┬─────┘    └────┬─────┘    └────┬─────┘  └───┬────┘
       │             │               │               │            │
       └─────────────┴───────────────┼───────────────┴────────────┘
                                     ▼
                              ┌───────────┐
                              │ frtb-     │
                              │  common   │
                              └───────────┘
```

**Allowed imports:** `frtb-*` capital components may import from `frtb-common`. `frtb-orchestration` may import from any sibling. **No other cross-package imports are allowed.** The root `import-linter` layers contract (`make import-lint`, part of `make quality-control`) enforces this graph in CI.

## Package responsibilities

### `frtb-common`

Shared primitives used by every capital component:

- `SignConvention` enum (loss-positive, profit-positive, magnitude).
- `ScenarioMetadata`, `ScenarioVector` containers.
- `RegulatoryPolicy` base class and `CalculationContext`.
- `DeskAuditRecord`, `CapitalRunAuditLog` framework.
- `BusinessCalendar` (when implemented).
- Logging configuration (`JSONFormatter`, `calculation_log_extra`).

Status: shared library. It provides shared status metadata, explicit
unsupported/unimplemented exception types, JSON-ready serialization, and
regulatory citation helpers. The migrated IMA package still holds some
calculation-specific abstractions inside `packages/frtb-ima`. Broader extraction
is a separate workstream.

### `frtb-ima` — Internal Models Approach

Capital from model-eligible trading desks. Inputs: 10-day scenario P&L vectors, RFET evidence, NMRF stress artifacts, PLA/backtesting vectors. Outputs: `CapitalComponents` per desk plus a `DeskEligibilityStatus` signal.

Migrated from `tomanizer/FRTB-IMA` with full history into
`packages/frtb-ima`.

Status: implemented public capital path with deterministic tests and validation
fixtures. Production regulatory use remains out of scope without independent
model validation and supervisory approval.

### `frtb-sbm` — Standardised Approach sensitivities-based method

Non-default standardised capital from delta, vega, and curvature sensitivities.
Inputs: canonical or CRIF-mapped sensitivities by risk class, bucket, tenor, and
risk measure. Outputs: SBM capital, risk-class totals, correlation-scenario
selection, and audit breakdowns.

Status: partial runtime. GIRR delta/vega, FX/equity/commodity/CSR delta/vega,
and row-wise curvature capital are implemented under BASEL_MAR21. Public
high-volume Arrow/batch capital entrypoints cover delta and GIRR vega; non-GIRR
vega and curvature capital remain row-wise. GIRR curvature has a validation-only
Arrow handoff. Public entry point: `calculate_sbm_capital`. Unsupported paths
fail closed; no silent zero-capital placeholders.

### `frtb-drc` — Default Risk Charge

Standardised default risk charge component. Jump-to-default capital for
non-securitisation, securitisation non-CTP, and correlation trading portfolio
positions. Inputs: issuer/tranche exposures, credit quality, seniority,
maturity, and JTD inputs. Outputs: DRC capital and issuer/tranche audit
breakdowns.

Status: partial runtime. The public API supports cited non-securitisation,
securitisation non-CTP, and CTP row paths with gross JTD, maturity scaling,
netting, bucket capital, reconciliation, and audit lineage. Securitisation
non-CTP and CTP risk weights and replication/decomposition evidence are
run-scoped inputs; missing evidence fails closed.

### `frtb-rrao` — Residual Risk Add-On

Standardised residual risk add-on component. Inputs: positions with exotic or
other residual risk classification evidence and gross effective notionals.
Outputs: additive RRAO capital, exclusion records, and contribution breakdowns.

Status: implemented for supported canonical-input profiles, including cited
classification, exclusions, deterministic subtotals, allocation helpers, and
audit/replay controls. Unsupported profiles and unsupported input paths fail
closed.

### `frtb-cva` — Credit Valuation Adjustment

CVA capital under the Basic Approach or Standardized Approach. Inputs: counterparty exposures, credit spreads, hedge positions.

Status: partial runtime. Reduced BA-CVA stand-alone and portfolio capital
implemented. SA-CVA GIRR delta weighting and aggregation implemented. Full
BA-CVA hedge recognition (MAR50.17–26) and SA-CVA risk classes other than
GIRR delta are unsupported and fail closed.

### `frtb-orchestration` — Suite aggregation

Combines IMA, SA component outputs, and CVA into firm-level capital figures.
For SA, it owns the composed `SBM + DRC + RRAO` total. For IMA fallback, it
routes non-IMA-eligible desks to the SA component stack. It also applies
cross-component floors and add-ons and produces consolidated audit records.

Status: partial. Public aggregation still raises explicit
unimplemented-component errors, but orchestration owns structural handoff
contracts for component outputs so SA composition can be added without sibling
capital packages importing each other.

## Why a monorepo

See [`decisions/0002-monorepo-structure.md`](decisions/0002-monorepo-structure.md). In short: one team, one product line, atomic cross-cutting changes, shared abstractions, consistent style. Per-package versioning and ADR-driven change control preserve SR 11-7 / PRA SS 1/23 model boundaries.

## Why SA components and CVA are separate packages

See [`decisions/0010-standardised-approach-component-taxonomy.md`](decisions/0010-standardised-approach-component-taxonomy.md).
`SA` is the regulatory composition label. `frtb-sbm`, `frtb-drc`, and
`frtb-rrao` are the implementation packages that together produce SA capital.
Each is a distinct model component under SR 11-7 with its own documentation
pack, but they share enough plumbing that a monorepo with separate packages is
the right factoring.

## Module documentation

Each capital component should have a suite-level documentation front door under
`docs/modules/<component>/`. For IMA, the formal model documentation pack lives
under [`docs/modules/frtb-ima/model_documentation/`](modules/frtb-ima/model_documentation/README.md)
and package-specific supporting evidence remains under `packages/frtb-ima/docs/`.
SBM and CVA have partial-runtime module documentation front doors. DRC has
partial-runtime planning and requirements documents, RRAO has a formal model
documentation pack, and orchestration/common have suite-support front doors. Formal model documentation
packs should be added or promoted when each capital package moves to an
implemented calculation maturity profile.

Model documentation packs cover:

- Intended use.
- Conceptual soundness.
- Derivation.
- Assumptions and limitations.
- Sensitivity analysis (validation-team deliverable).
- Monitoring plan.
- Change history.

Machine-readable package maturity and crosswalk status live in
[`docs/quality/PACKAGE_STATUS.md`](quality/PACKAGE_STATUS.md), generated from
[`package_maturity.toml`](quality/package_maturity.toml).

This structure supports independent SR 11-7 validation per component.

## Versioning

- Each package has its own `version` in its `pyproject.toml`.
- The workspace itself has a `version` for tooling identification only.
- Releases coordinate package versions; the suite-level `CHANGELOG.md` records the combined release.

## Development workflow

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for material-change policy, ADR requirements, and review standards.
