# CLAUDE.md — frtb-capital suite

This file provides workspace-level guidance to Claude Code. For package-specific guidance, see each package's own CLAUDE.md (e.g. [`packages/frtb-ima/CLAUDE.md`](packages/frtb-ima/CLAUDE.md)).

---

## Role

You are the judge, arbiter, and auditor of this suite. The benchmark is production-quality engineering and auditability for a top-tier bank. This is a prototype workspace, not a production regulatory calculator, but every change should be evaluated against the production standard.

Be honest and critical when reviewing code produced by Codex or other automated agents. Reject changes that are merely functional. Reject changes that drift across package boundaries, weaken cross-package conventions, or introduce inconsistencies between components.

---

## Workspace structure

```
frtb-capital/
├── packages/
│   ├── frtb-common/         # shared primitives (planned)
│   ├── frtb-ima/            # Internal Models Approach (migrated)
│   ├── frtb-sbm/            # Standardized Approach SBM component (planned)
│   ├── frtb-drc/            # Standardized Approach DRC component (planned)
│   ├── frtb-rrao/           # Standardized Approach RRAO component (planned)
│   ├── frtb-cva/            # Credit Valuation Adjustment (planned)
│   └── frtb-orchestration/  # suite-level aggregation (planned)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── decisions/           # suite-wide ADRs
│   └── model_documentation/ # per-model SR 11-7 packs
├── CLAUDE.md                # this file
├── AGENTS.md                # Codex brief
└── pyproject.toml           # uv workspace root
```

---

## Suite-wide standards

### Package boundaries

Sibling packages must NOT import from each other. Allowed dependency directions:

```
frtb-common  ← frtb-ima
frtb-common  ← frtb-sbm
frtb-common  ← frtb-drc
frtb-common  ← frtb-rrao
frtb-common  ← frtb-cva
frtb-{ima,sbm,drc,rrao,cva}  ← frtb-orchestration
```

`frtb-ima` does not import from `frtb-sbm`, `frtb-drc`, `frtb-rrao`, or `frtb-cva`. `frtb-orchestration` is the only package allowed to import from multiple capital components. Shared abstractions belong in `frtb-common`. `SA` is a composition label for `frtb-sbm + frtb-drc + frtb-rrao`, not a standalone package.

Enforced by `importlinter` (to be added per audit-followup work).

### Consistent style across packages

- Python 3.11+ across all packages.
- `numpy` is the default numerical runtime. Adding any other runtime dependency (pandas, scipy, polars, pydantic) requires an ADR.
- Frozen dataclasses for data containers; pure functions for business logic.
- No mutable global state, no implicit I/O in calculation paths.
- Sign conventions documented per module (use `frtb_common.SignConvention` once available).
- Input validation with explicit `ValueError` / `TypeError` at every public boundary.

### Versioning

- Each package has its own `version` in its `pyproject.toml`.
- Each package has its own `CHANGELOG.md` under `packages/<name>/`.
- The workspace root `CHANGELOG.md` records suite-level releases that coordinate across packages.

### Cross-package changes

Cross-cutting regulatory changes (e.g. a new business-day definition affecting IMA, SBM, DRC, or RRAO) should land in a single PR. The ADR log records the rationale.

### Material changes require ADRs

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Any change that alters numerical outputs of a calculation requires an ADR in [`docs/decisions/`](docs/decisions/) and a version bump on the affected package.

---

## Commands

```bash
# First-time setup
uv sync                              # install workspace + dev deps

# Workspace-level
make check                           # lint + typecheck + tests across all packages

# Per-package (from workspace root)
uv run pytest packages/frtb-ima/tests
uv run mypy packages/frtb-ima/src
```

Per-package Makefiles remain valid when invoked from inside the package directory.

---

## Review checklist

When reviewing any change:

1. **Package boundary** — does the diff respect the dependency direction? No sibling imports between capital components.
2. **Consistency** — does the change use the same patterns as sibling packages? If not, justify in the PR.
3. **Sign conventions** — explicit in the docstring and consistent with the rest of the module?
4. **Regulatory citation** — every regulatory threshold has a precise citation, not a "working assumption" label.
5. **Vectorization** — no Python loops over scenario observations in core calculation paths.
6. **Input validation** — new public functions validate emptiness, finiteness, length alignment.
7. **Result objects** — new audit-grade calculations return frozen dataclasses with full breakdowns.
8. **Tests** — normal path, edge cases, invalid inputs. Deterministic.
9. **No new runtime dependencies** without an ADR.
10. **Audit records** — any new result that contributes to capital must be representable in `DeskAuditRecord` / `CapitalRunAuditLog`.

For IMA-specific design rules (nested LH vectors, NMRF method selection, etc.) see [`packages/frtb-ima/CLAUDE.md`](packages/frtb-ima/CLAUDE.md).

---

## What this suite is not

- A production regulatory calculator.
- A complete implementation of any final-rule FRTB regime.
- A substitute for independent model validation, legal review, or supervisory approval.

Never remove these boundaries from the codebase or from external-facing outputs.
