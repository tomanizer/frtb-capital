# CLAUDE.md — frtb-capital suite

This file provides workspace-level guidance to Claude Code. For package-specific guidance, see each package's own CLAUDE.md (e.g. [`packages/frtb-ima/CLAUDE.md`](packages/frtb-ima/CLAUDE.md)).

---

## Agent workspace policy

The protected main clone is the local checkout that owns the `main` worktree.
Keep it on `main` and synced to `origin/main`; do not edit, commit, or switch
branches in that clone. By default, normal agent work happens in a sibling
worktree root named `<protected-main-dir>-worktrees`, using paths like
`<worktree-root>/<agent>/<task>` on a branch named `<agent>/<task>`.

The worktree helper discovers the protected main clone from Git's worktree
metadata. If local policy needs an explicit path, set repo-local Git config:

```bash
git config --local frtb.agentMainClone /path/to/frtb-capital
git config --local frtb.agentWorktreeRoot /path/to/frtb-capital-worktrees
```

`FRTB_AGENT_MAIN_CLONE` and `FRTB_AGENT_WORKTREE_ROOT` may be used for
environment-specific overrides.

Before editing, run `python3 scripts/agent_worktree.py guard` from the current
checkout. If it fails, create a compliant worktree with
`make agent-new AGENT=claude TASK=<task-name>` and move there. Use
`make agent-sync-main` to fast-forward the protected main clone and
`make agent-worktrees` to list existing worktrees. See
[`docs/AGENT_WORKTREE_POLICY.md`](docs/AGENT_WORKTREE_POLICY.md).

---

## Role

You are the judge, arbiter, and auditor of this suite. The benchmark is production-quality engineering and auditability for a top-tier bank. This is a prototype workspace, not a production regulatory calculator, but every change should be evaluated against the production standard.

Be honest and critical when reviewing code produced by Codex or other automated agents. Reject changes that are merely functional. Reject changes that drift across package boundaries, weaken cross-package conventions, or introduce inconsistencies between components.

---

## Workspace structure

```
frtb-capital/
├── packages/
│   ├── frtb-common/         # shared primitives
│   ├── frtb-ima/            # Internal Models Approach (implemented)
│   ├── frtb-sbm/            # Standardized Approach SBM (partial runtime)
│   ├── frtb-drc/            # Standardized Approach DRC (partial runtime)
│   ├── frtb-rrao/           # Standardized Approach RRAO (implemented)
│   ├── frtb-cva/            # Credit Valuation Adjustment (partial runtime)
│   ├── frtb-orchestration/  # suite-level aggregation (implemented)
│   └── frtb-result-store/   # DuckDB/Parquet evidence store (partial)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── decisions/           # suite-wide ADRs
│   └── modules/             # component docs and model documentation packs
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

Enforced by `import-linter` via the root `[tool.importlinter]` layers contract
(`make import-lint`, included in `make quality-control`).

### Consistent style across packages

- Python 3.11+ across all packages.
- `numpy` is the numerical runtime for capital calculation kernels. `pyarrow`
  is approved only for tabular handoff, IO, CRIF normalization, adapters, and
  handoff objects under
  [`ADR 0023`](docs/decisions/0023-arrow-tabular-handoff-boundary.md).
  Kernels must not import `pyarrow`, `pandas`, or `polars`; the
  `quality-control` target enforces this. Other runtime dependencies (`pandas`,
  `scipy`, `polars`, `statsmodels`, `pydantic`, etc.) require an ADR before
  entering the runtime path. These libraries may be used in notebooks,
  validation, tests, research, or optional adapters when they do not leak into
  the core runtime path; see
  [`ADR 0011`](docs/decisions/0011-core-runtime-dependency-policy.md).
- Frozen dataclasses for data containers; pure functions for business logic.
- No mutable global state, no implicit I/O in calculation paths.
- Sign conventions documented per module (use `frtb_common.SignConvention` once available).
- Input validation with explicit `ValueError` / `TypeError` at every public boundary.

### Versioning

- Each package has its own `version` in its `pyproject.toml`.
- Each package has its own `CHANGELOG.md` under `packages/<name>/`.
- The workspace root `CHANGELOG.md` records suite-level releases that coordinate across packages.
- **Feature and fix PRs must not bump `version =` or add release sections to CHANGELOG.md.**
  Instead, add a changelog fragment to `packages/<pkg>/changelog.d/<pr-number>.<type>.md`.
  Version bumps and changelog assembly happen in a `release/*` PR. See
  [ADR 0015](docs/decisions/0015-deferred-versioning-and-changelog-fragments.md) and
  [CONTRIBUTING.md](CONTRIBUTING.md#changelog-fragments).
- CI will reject any non-`release/*` PR that bumps a package version or regenerates
  `uv.lock` without a corresponding dependency-spec change.

### Cross-package changes

Cross-cutting regulatory changes (e.g. a new business-day definition affecting IMA, SBM, DRC, or RRAO) should land in a single PR. The ADR log records the rationale.

### Material changes require ADRs

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Any change that alters numerical outputs of a calculation requires an ADR in [`docs/decisions/`](docs/decisions/) and a version bump on the affected package.

---

## CI babysit

When asked to babysit a pull request through CI and bot reviews, read and execute:

- [`.grok/skills/frtb-ci-babysit/SKILL.md`](.grok/skills/frtb-ci-babysit/SKILL.md)

Or run `/frtb-ci-babysit` ([`.claude/commands/frtb-ci-babysit.md`](.claude/commands/frtb-ci-babysit.md)).

## Documentation audits

When asked to audit or align package documentation across the suite, read and
execute:

- [`.grok/skills/frtb-doc-audit/SKILL.md`](.grok/skills/frtb-doc-audit/SKILL.md)
- [`.grok/skills/frtb-doc-audit/references/audit-checklist.md`](.grok/skills/frtb-doc-audit/references/audit-checklist.md)

Or run the Claude command `/frtb-doc-audit` (wrapper:
[`.claude/commands/frtb-doc-audit.md`](.claude/commands/frtb-doc-audit.md)).
Use `make agent-new AGENT=claude TASK=<task-name>` when the worktree guard fails.

## Simplification audits

When asked to audit code maintainability (complexity, wrappers, duplication),
read and execute:

- [`.grok/skills/frtb-simplify-audit/SKILL.md`](.grok/skills/frtb-simplify-audit/SKILL.md)
- [`docs/quality/simplification/rubric.md`](docs/quality/simplification/rubric.md)
- [`docs/quality/simplification/2026-06-04/`](docs/quality/simplification/2026-06-04/) (latest suite run)

Or run `/frtb-simplify-audit` ([`.claude/commands/frtb-simplify-audit.md`](.claude/commands/frtb-simplify-audit.md)).
Default is audit-only; implementation refactors are one package per PR.

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
