# frtb-capital architecture

## Suite overview

`frtb-capital` is a workspace of FRTB market-risk capital calculation packages. It implements the four primary capital charges plus a suite-level aggregator, with a shared foundation package.

## Dependency graph

```
                   ┌────────────────────────┐
                   │   frtb-orchestration   │   top-of-the-house aggregation
                   └─────────┬──────────────┘
                             │
       ┌────────┬────────────┼────────────┬─────────┐
       ▼        ▼            ▼            ▼         ▼
   ┌────────┐ ┌──────┐  ┌────────┐  ┌────────┐
   │ frtb-  │ │frtb- │  │ frtb-  │  │ frtb-  │
   │  ima   │ │  sa  │  │  drc   │  │  cva   │
   └───┬────┘ └──┬───┘  └───┬────┘  └───┬────┘
       │         │          │           │
       └─────────┴────┬─────┴───────────┘
                      ▼
                ┌───────────┐
                │ frtb-     │   shared primitives
                │  common   │
                └───────────┘
```

**Allowed imports:** `frtb-*` capital components may import from `frtb-common`. `frtb-orchestration` may import from any sibling. **No other cross-package imports are allowed.**

## Package responsibilities

### `frtb-common`

Shared primitives used by every capital component:

- `SignConvention` enum (loss-positive, profit-positive, magnitude).
- `ScenarioMetadata`, `ScenarioVector` containers.
- `RegulatoryPolicy` base class and `CalculationContext`.
- `DeskAuditRecord`, `CapitalRunAuditLog` framework.
- `BusinessCalendar` (when implemented).
- Logging configuration (`JSONFormatter`, `calculation_log_extra`).

Status: skeleton planned. Currently each component holds its own copy of these abstractions inside `frtb-ima`. Extraction is a separate workstream.

### `frtb-ima` — Internal Models Approach

Capital from model-eligible trading desks. Inputs: 10-day scenario P&L vectors, RFET evidence, NMRF stress artifacts, PLA/backtesting vectors. Outputs: `CapitalComponents` per desk plus a `DeskEligibilityStatus` signal.

Migrated from `tomanizer/FRTB-IMA` with full history.

Status: substantial implementation. Audit-followup issues track the path to a B-grade production-ready engine.

### `frtb-sa` — Standardized Approach

Sensitivity-based capital. Inputs: delta, vega, curvature sensitivities per risk class. Outputs: SA capital per desk.

Status: planned. Not started.

### `frtb-drc` — Default Risk Charge

Jump-to-default capital for non-securitization, securitization non-CTP, and CTP. Inputs: issuer exposures, ratings, JTD calculations. Outputs: DRC capital per desk.

Status: planned. Not started.

### `frtb-cva` — Credit Valuation Adjustment

CVA capital under the Basic Approach or Standardized Approach. Inputs: counterparty exposures, credit spreads, hedge positions.

Status: planned. Not started.

### `frtb-orchestration` — Suite aggregation

Combines the four capital outputs into a firm-level capital figure, applies floors and add-ons (e.g. IMA vs SA floor, PLA add-on), produces consolidated audit records.

Status: planned. Not started.

## Why a monorepo

See [`decisions/0002-monorepo-structure.md`](decisions/0002-monorepo-structure.md). In short: one team, one product line, atomic cross-cutting changes, shared abstractions, consistent style. Per-package versioning and ADR-driven change control preserve SR 11-7 / PRA SS 1/23 model boundaries.

## Why SA, DRC, CVA are separate packages (not separate repos)

See [`decisions/0003-sa-drc-cva-scope.md`](decisions/0003-sa-drc-cva-scope.md). Each is a distinct model under SR 11-7 with its own documentation pack, but they share enough plumbing (audit records, business calendar, regulatory policy framework) that a monorepo with separate packages is the right factoring.

## Per-model documentation

Each capital component has its own model documentation pack under `docs/model_documentation/<component>/`. The pack covers:

- Intended use.
- Conceptual soundness.
- Derivation.
- Assumptions and limitations.
- Sensitivity analysis (validation-team deliverable).
- Monitoring plan.
- Change history.

This structure supports independent SR 11-7 validation per component.

## Versioning

- Each package has its own `version` in its `pyproject.toml`.
- The workspace itself has a `version` for tooling identification only.
- Releases coordinate package versions; the suite-level `CHANGELOG.md` records the combined release.

## Development workflow

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for material-change policy, ADR requirements, and review standards.
