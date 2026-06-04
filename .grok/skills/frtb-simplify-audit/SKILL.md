---
name: frtb-simplify-audit
description: >-
  Audit frtb-capital package source for maintainability: overlong files and
  functions, deep nesting, useless wrappers, duplication, and simplification
  opportunities. Produces per-package reports and optional tracking PR/issues.
when-to-use: >-
  Use when asked for a simplification audit, code maintainability review,
  wrapper cleanup assessment, complexity audit, or runs /frtb-simplify-audit.
argument-hint: "[--report-only | --issues] [--agent <name>] [--date YYYY-MM-DD]"
allowed-tools: Read, Grep, Glob, Shell, Write, StrReplace, Delete, Task
---

# FRTB simplification audit

Audit **all workspace packages** for code simplification and maintainability.
This is **audit-only by default** — do not refactor runtime code unless the user
explicitly requests `--fix` (not part of the default workflow).

Read `.grok/skills/frtb-capital/SKILL.md`, `AGENTS.md`, `CLAUDE.md`, and
`docs/quality/simplification/rubric.md` first.

## Cross-agent entrypoints

| Agent | Entry |
| --- | --- |
| Grok | `/frtb-simplify-audit` (this skill) |
| Claude Code | `/frtb-simplify-audit` → `.claude/commands/frtb-simplify-audit.md` |
| Codex | `AGENTS.md` → Simplification audits section |
| Cursor | `.cursor/rules/frtb-capital.mdc` |
| GitHub Copilot | `.github/copilot-instructions.md` |

## Arguments

| Flag | Default | Meaning |
| --- | --- | --- |
| `--report-only` | on | Write reports only; no GitHub issues or PR |
| `--issues` | off | Create one tracking issue per package (requires `gh`) |
| `--agent <name>` | `grok` | Worktree agent id for `make agent-new` |
| `--date <YYYY-MM-DD>` | today | Report directory under `docs/quality/simplification/` |

If `--issues` is set, also open a docs/governance PR that adds the skill, reports,
and cross-agent entrypoints. Implementation refactors stay in **separate**
package-scoped PRs.

## Step 1 — Compliant checkout

```bash
make agent-ensure AGENT=<agent> TASK=simplify-audit
```

If not already in a compliant worktree, this creates or reuses one and prints
`next: cd ...` — **change directory there before any edit**. Never commit from
the protected main clone (`~/Documents/Projects/frtb-capital`).

## Step 2 — Package inventory

Read `docs/quality/package_maturity.toml`. Audit these eight packages in order:

1. `frtb-common`
2. `frtb-cva`
3. `frtb-drc`
4. `frtb-ima`
5. `frtb-orchestration`
6. `frtb-result-store`
7. `frtb-rrao`
8. `frtb-sbm`

SA is not a package (`SBM + DRC + RRAO` via orchestration).

## Step 3 — Required mechanical checks

From `references/audit-checklist.md`:

```bash
uv run python scripts/ci/check_simplification_drift.py
find packages -path '*/src/*' -name '*.py' -print | xargs wc -l | sort -nr | head -40
```

Run the rubric `rg` patterns in `docs/quality/simplification/rubric.md`. When
possible, run an AST scan for:

- functions over **120** lines;
- files over **500** lines (flag over **1000** as P0/P1);
- nesting depth **≥ 5**;
- trivial `return other_fn(...)` wrappers (especially repeated SBM batch builders).

## Step 4 — Per-package pass (sequential)

For **each** package, write
`docs/quality/simplification/<date>/<package>.md` using
`references/report-template.md`.

Cover:

- Hotspot map (file LOC, longest functions)
- Duplicated code (in-package and cross-package)
- Dead / storage-only / placeholder code
- `frtb-common` candidates (mechanics only)
- Package-local factoring candidates
- Over-complexity and nested logic
- Useless or table-collapsible wrappers
- What must not move (regulatory semantics)
- Recommended sequence (package-scoped PRs)
- Validation before any refactor

Classify every finding: scope (`audit-only`, `package-local`, `frtb-common`,
`ADR-required`) and priority (`P0`–`P3`). See rubric.

## Step 5 — Suite summary

Write `docs/quality/simplification/<date>/README.md` with:

- Cross-package P0/P1 table
- Implementation order (hash migration → local helpers → batch splits)
- Links to per-package reports
- Pointer to `docs/quality/REFACTOR_HOTSPOTS.md`

## Step 6 — Tracking issues (optional)

When `--issues` is set, create **one GitHub issue per package** with title
`Simplification follow-up: <package> (<date>)` and body:

- Link to `docs/quality/simplification/<date>/<package>.md`
- Top 3 P0/P1 bullets
- Label: use existing `enhancement` or `tech-debt` if available; otherwise none

Record issue numbers in the suite `README.md` under `## Tracking issues`.

## Step 7 — Governance PR (when `--issues`)

Branch `<agent>/simplify-audit`. PR body:

- Summary of audit-only deliverable
- `Closes #N` for each tracking issue **only if** this PR itself implements
  fixes (it should not — list issues as related links instead)
- Verification: `make docs-check` (docs-only)

Do not bump package versions (ADR 0015).

## Final output

Deliver to the user:

- Path to suite `README.md`
- Per-package report paths
- `check_simplification_drift.py` result (pass/fail summary)
- Issue URLs if created
- PR URL if opened

## Related artifacts

- Rubric: `docs/quality/simplification/rubric.md`
- Prior run: `docs/quality/simplification/2026-06-02/`
- Hotspots: `docs/quality/REFACTOR_HOTSPOTS.md`
- Drift gate: `scripts/ci/check_simplification_drift.py`
