# AGENTS.md — frtb-capital suite

Guidance for Codex and other coding agents working in this workspace. Package-specific briefs live under each package (e.g. [`packages/frtb-ima/AGENTS.md`](packages/frtb-ima/AGENTS.md)).

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

Before editing, run `make agent-ensure AGENT=<agent> TASK=<task-name>` from any
checkout of this repo (including the protected main clone). The command passes
when already in a compliant worktree; otherwise it creates or reuses
`<worktree-root>/<agent>/<task>` and prints `next: cd ...` — **change directory
there before changing files**. Equivalent:
`python3 scripts/agent_worktree.py ensure --agent <agent> <task-name>`.
Use `make agent-sync-main` to fast-forward the protected main clone and
`make agent-worktrees` to list existing worktrees. See
[`docs/AGENT_WORKTREE_POLICY.md`](docs/AGENT_WORKTREE_POLICY.md).

## Project identity

This is a `uv` workspace containing a suite of FRTB market-risk capital calculation packages. Each package implements one capital component (IMA, SBM, DRC, RRAO, CVA) plus a shared `frtb-common` library and a suite-level orchestration layer. SA is the composed Standardised Approach total from SBM, DRC, and RRAO, not a standalone package.

The goal is a transparent, testable prototype suite that demonstrates how an existing risk engine could generate scenario P&L, sensitivity, default-risk, residual-risk, and credit exposure inputs that an ex-post capital layer assembles into IMA, SA component stack, CVA, and top-of-the-house aggregate capital.

## Scope

- **In scope:** IMA, SBM, DRC, RRAO, CVA capital calculation; SA composition in orchestration; suite-level aggregation; shared abstractions.
- **Out of scope:** market data sourcing, pricing engines, regulatory submission packaging, firm-level financial reporting (beyond capital aggregation).

## Regulatory caution

All U.S. NPR 2.0 / Basel FRTB / EU CRR3 / PRA UK CRR content is proposed-rule or comparison material. Do not present outputs as final regulatory capital. Cite specific regulatory paragraphs, not framework names.

## Coding style

- Python 3.11+ across all packages.
- Prefer dataclasses, enums, pure functions.
- `numpy` is the runtime numerical dependency for capital calculation kernels.
  `pyarrow` is approved only for tabular handoff, IO, CRIF normalization,
  adapters, and handoff objects under
  [`ADR 0023`](docs/decisions/0023-arrow-tabular-handoff-boundary.md).
  Kernels must not import `pyarrow`, `pandas`, or `polars`; the
  `quality-control` target enforces this. `pandas`, `polars`, `scipy`, and
  `statsmodels` may be used in notebooks, validation, tests, research, or
  optional adapters when they do not leak into the core runtime path; see
  [`ADR 0011`](docs/decisions/0011-core-runtime-dependency-policy.md).
- Add unit tests for every calculation.
- Synthetic data only; no proprietary market data.
- Favour clarity over cleverness.
- Runtime package modules and public APIs must be documented according to
  [`docs/quality/documentation_rules.md`](docs/quality/documentation_rules.md):
  module docstrings explain file role and package boundary, public callable
  docstrings use meaningful NumPy-style sections where applicable, and
  domain-significant private helpers document regulatory, audit, aggregation,
  unsupported-feature, or attribution behavior.
- Cite regulatory paragraphs explicitly; do NOT use phrases like "working assumption" or "prototype" as a substitute for citation.
- Preserve attribution readiness for every capital component: stable ids,
  deterministic grouping, intermediate audit records, and branch metadata must
  make later analytical Euler or impact analysis possible without changing the
  capital number. See [`ADR 0012`](docs/decisions/0012-capital-impact-attribution.md).

## Workspace discipline

- **No sibling imports between capital packages.** `frtb-ima` must not import from `frtb-sbm`, `frtb-drc`, `frtb-rrao`, `frtb-cva`, etc. Shared types go in `frtb-common`.
- **One package per PR** unless the change is genuinely cross-cutting (regulatory definition change, shared type update). Cross-cutting PRs must reference an ADR.
- **Per-package versioning.** Bump only the affected package's version.
- **Material changes need ADRs.** See [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **Close all sub-issues explicitly in the PR body.** GitHub only closes issues
  named directly in the PR body with `Closes #N`. Checkboxes inside a parent
  issue (`- [x] #N`) are not followed. When a PR closes a parent/phase issue,
  list every delivered sub-issue with its own `Closes #N` line — do not rely on
  the parent's checkbox list. The `cascade-close-subissues` action is a fallback,
  not a substitute for explicit closing references.

## Quality control plane

- Run `make agent-guard` and `make quality-control` before pushing any branch
  that changes package code, package metadata, model documentation, regulatory
  traceability, CI controls, or repository governance files.
- Run `make drift-check`, `make changed-code-check`, `make test-value-check`,
  and `make dead-code-check` before committing substantial generated or
  refactoring changes. If the code-drift baseline must grow, update it with
  `make drift-baseline` and make the baseline diff explicit in the PR.
- For substantive package changes, run make ci-local (or at minimum
  make check) before push. Use Python 3.11 locally (via .python-version)
  so results match CI; newer interpreters can fail fixture hash gates such as
  frtb-drc drc_nonsec_v2.
- If the full suite is impractical, run the affected package tests plus
  `make quality-control`, and state the narrower validation in the PR.
- Keep [`docs/quality/package_maturity.toml`](docs/quality/package_maturity.toml)
  in sync with package additions, removals, renames, or implementation-status
  changes. Every package under `packages/` must be represented exactly once in
  the registry.
- Do not satisfy maturity gates with placeholder evidence. If documentation,
  tests, citations, or public entrypoints are not ready, keep the package at the
  lower maturity profile until real evidence exists.
- Public package contracts referenced by the maturity registry must be top-level
  imports, such as `frtb_<x>:PACKAGE_METADATA` and public calculation entrypoints.
  Avoid relying on private modules to satisfy registry gates.
- Add package-local tests for new runtime behavior and reference the relevant
  tests in the package maturity registry when the maturity gate depends on them.
- Treat the remote `quality-control` CI job as mandatory. Fix failures before
  review or merge, and do not bypass the check without a documented governance
  reason.

### Local CI presets for agents

Run `make agent-guard` before validation. Prefer these presets over ad hoc command
bundles, and list the exact preset or narrower substitute in the PR body:

- `make ci-local-pr` — ordinary package code, tests, fixtures, scripts, examples,
  adapters, or focused refactors. Runs changed pytest targets, mandatory
  governance checks, and strict changed-code/test-value/dead-code guards.
- `make ci-local-governance` — CI workflow, repository governance, docs quality,
  dependency/SBOM, examples, notebook, or agent-instruction changes. Mirrors the
  broad local CI surface and adds `quality-control`.
- `make ci-local-performance` — vectorization, batch, adapter, benchmark,
  memory/performance-sensitive, or scaling-sensitive changes. Runs changed tests,
  the benchmark suite, benchmark budgets, and `quality-control`.
- `make ci-local-release` — release-readiness, pre-merge hardening, broad
  cross-package changes, or final audit before a high-risk merge. Runs the full
  local CI surface, `quality-control`, partial-runtime coverage, benchmark suite,
  and benchmark budgets.

If a preset is impractical, run the most relevant narrower commands, explain why
the preset was skipped, and include that validation gap in the PR.

## CI babysit

When asked to babysit, watch, or bring a PR to merge-ready (CI green, Gemini and
Copilot feedback, final audit), follow:

- [`.grok/skills/frtb-ci-babysit/SKILL.md`](.grok/skills/frtb-ci-babysit/SKILL.md)

Grok: `/frtb-ci-babysit`. Claude Code: `/frtb-ci-babysit` →
[`.claude/commands/frtb-ci-babysit.md`](.claude/commands/frtb-ci-babysit.md).

Requires `gh` and a compliant worktree (`make agent-ensure AGENT=<agent> TASK=<task>`).
Use `grok`, `claude`, `codex`, `cursor`, or `copilot` as the agent id; `cd` to the
printed worktree before editing.

## Documentation audits

When asked to audit package documentation, check whether docs match code, or
fix stale README/agent/architecture text, follow the shared workflow (all agents,
all worktree names):

- [`.grok/skills/frtb-doc-audit/SKILL.md`](.grok/skills/frtb-doc-audit/SKILL.md)
- [`.grok/skills/frtb-doc-audit/references/audit-checklist.md`](.grok/skills/frtb-doc-audit/references/audit-checklist.md)

Grok: `/frtb-doc-audit` or `/frtb-doc-audit --report-only`. Claude Code:
`/frtb-doc-audit` (see [`.claude/commands/frtb-doc-audit.md`](.claude/commands/frtb-doc-audit.md)).

Use `--agent codex` (or `claude`, `cursor`, `copilot`) in the skill when creating
a worktree. Documentation-only PRs do not bump package versions (ADR 0015).

## Simplification audits

When asked to audit code maintainability (overlong files/functions, wrappers,
duplication, complexity), follow:

- [`.grok/skills/frtb-simplify-audit/SKILL.md`](.grok/skills/frtb-simplify-audit/SKILL.md)
- [`docs/quality/simplification/rubric.md`](docs/quality/simplification/rubric.md)
- Latest reports: [`docs/quality/simplification/2026-06-04/`](docs/quality/simplification/2026-06-04/)

Grok: `/frtb-simplify-audit`. Claude Code: `/frtb-simplify-audit` →
[`.claude/commands/frtb-simplify-audit.md`](.claude/commands/frtb-simplify-audit.md).

Default is **audit-only** (reports, no runtime edits). Use `--issues` to open
per-package tracking issues. Implementation refactors stay **one package per PR**;
run `uv run python scripts/ci/check_simplification_drift.py` before wrapper changes.

## Review focus

When reviewing or changing code, focus on:

- Package boundary discipline (no sibling imports).
- Consistency of style across packages.
- Regulatory citations in place of "working assumption" language.
- Correct scenario-vector granularity in IMA, correct bucket aggregation in SBM, correct issuer aggregation in DRC, correct residual-risk classification in RRAO, correct exposure-at-default treatment in CVA.
- Deterministic tests; no random seeds without fixing them.
- Frozen dataclasses for audit-grade results.
- Explicit `UnsupportedRegulatoryFeatureError` where a regime is not implemented; never silent computation.
- Audit-record compatibility for any new result that contributes to capital.
- Attribution/impact compatibility for any new capital aggregation branch,
  including explicit residual or unsupported-method behavior where exact Euler
  decomposition is not valid.
