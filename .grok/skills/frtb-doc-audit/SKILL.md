---
name: frtb-doc-audit
description: >-
  Systematically audit and align frtb-capital package documentation with code,
  maturity registry, and ADRs. Produces a per-package report and optional doc-fix
  PR in a compliant agent worktree.
when-to-use: >-
  Use when the user asks for a documentation audit, doc review, stale docs check,
  whether docs match code, package README review, or runs /frtb-doc-audit.
  Also use before large doc-only PRs to prevent orchestration/scaffold drift.
argument-hint: "[--report-only | --fix] [--agent <name>]"
allowed-tools: Read, Grep, Glob, Shell, Write, StrReplace, Delete, Task, SwitchMode
---

# FRTB documentation audit

You audit **all workspace packages** in `frtb-capital` for documentation accuracy,
completeness, and professionalism. Optionally open a doc-fix PR.

Read `.grok/skills/frtb-capital/SKILL.md`, `AGENTS.md`, and `CLAUDE.md` first.
Documentation-only changes do not bump package versions (ADR 0015).

## Cross-agent entrypoints

This skill is the single source of truth. Other agents reach it via:

| Agent | Entry |
| --- | --- |
| Grok | `/frtb-doc-audit` (this skill) |
| Claude Code | `/frtb-doc-audit` → `.claude/commands/frtb-doc-audit.md` |
| Codex | `AGENTS.md` → Documentation audits section |
| Cursor | `.cursor/rules/frtb-capital.mdc` |
| GitHub Copilot | `.github/copilot-instructions.md` |

All agents use the same worktree policy; set `--agent` to match the active agent
when creating a worktree (`codex`, `claude`, `cursor`, `copilot`, `grok`).

## Arguments

Parse the user message:

| Flag | Default | Meaning |
| --- | --- | --- |
| `--report-only` | off | Audit and report only; do not edit files |
| `--fix` | on when user asked to fix or open PR | Apply fixes and open/update a PR |
| `--agent <name>` | `grok` | Agent id for `make agent-new AGENT=...` |

If both `--report-only` and `--fix` appear, `--report-only` wins.

## Step 1: Compliant checkout

**Success criteria:** a compliant worktree is active before any file edit.

1. Run `make agent-ensure AGENT=<agent> TASK=doc-audit-fix` from any checkout
   (including protected `main`).
2. If the command prints `next: cd ...`, change directory there before continuing.
3. If already in `<worktree-root>/<agent>/doc-audit-fix` on branch
   `<agent>/doc-audit-fix`, the command passes in place.
4. Never commit or push from the protected main clone.

## Step 2: Package inventory

**Success criteria:** Table of every package in `docs/quality/package_maturity.toml`
with `package`, `maturity`, `module_docs`, and `calculation_entrypoint` (if any).

1. Read `docs/quality/package_maturity.toml` and `docs/modules/README.md`.
2. List all `packages/*/pyproject.toml` paths; confirm count matches the registry
   (currently eight: common, ima, sbm, drc, rrao, cva, orchestration, result-store).
3. Note SA is **not** a package; it is `SBM + DRC + RRAO` in orchestration.

## Step 3: Per-package documentation pass

**Success criteria:** For each package, a short subsection covering: up to date,
code-aligned, stale signals, completeness, professionalism, helpfulness, gaps.

For **each** package, inspect in parallel where possible:

| Layer | Paths |
| --- | --- |
| Package front door | `packages/<pkg>/README.md`, `AGENTS.md`, `CLAUDE.md` |
| Module docs | `docs/modules/<pkg>/` (README, PUBLIC_API.md, model_documentation/) |
| Package-local docs | `packages/<pkg>/docs/` when present |
| Public surface | `packages/<pkg>/src/*/__init__.py` (`__all__`, entrypoints) |
| Maturity | `docs/quality/package_maturity.toml` row for the package |

**Checklist** (see `references/audit-checklist.md`):

- README status matches `package_maturity.toml` and actual code.
- `AGENTS.md` / `CLAUDE.md` do not describe implemented APIs as scaffold-only.
- `docs/modules/<pkg>/PUBLIC_API.md` matches top-level exports (RRAO is the template).
- No contradictory claims between `docs/ARCHITECTURE.md`, package README, and module README.
- ADRs referenced by docs still match behaviour; add or amend ADR when docs describe
  new implemented behaviour (e.g. orchestration `calculate_suite_capital`).
- Stale grep targets: `scaffolded`, `NotImplemented`, `unimplemented`, `does not calculate`,
  `remains explicitly unimplemented`, `row-wise only` (verify against SBM batch exports).

**Package-specific notes:**

- **frtb-orchestration:** `docs/modules/frtb-orchestration/README.md` is canonical;
  package README and agent briefs must agree.
- **frtb-ima:** Large `__all__`; PUBLIC_API may summarize; `__all__` is source of truth.
- **frtb-common / result-store:** No capital formulae; storage boundary must stay clear.

## Step 4: Cross-cutting and suite index

**Success criteria:** List of repo-wide stale docs and `docs/DOCUMENTATION_AUDIT.md`
assessment (exists, dated, complete).

1. Read `docs/ARCHITECTURE.md` intro and each package section.
2. Read `docs/DOCUMENTATION_AUDIT.md`; note if it understates implemented packages.
3. Read root `CLAUDE.md` workspace tree; all packages should appear with accurate maturity.
4. Read `docs/modules/MODEL_DOCUMENTATION_PROMOTION_PLAN.md` for model-doc gaps.

## Step 5: Deliver audit report

**Success criteria:** User receives a structured markdown report with a summary matrix
and prioritized fix list (P0 contradictions, P1 missing PUBLIC_API/agent briefs, P2 polish).

Report sections:

1. Package inventory table
2. Per-package audit (use quality matrix: up to date / aligned / complete / professional / helpful)
3. Cross-cutting findings
4. Recommended fix order

**Human checkpoint:** If `--report-only`, stop after the report.

## Step 6: Doc-fix PR (when `--fix`)

**Success criteria:** Branch pushed; PR opened or updated; only documentation and ADR
files changed unless user explicitly asked for code.

Apply fixes in priority order:

1. **P0 contradictions** — orchestration, ARCHITECTURE, ADR cross-refs
2. **ADRs** — add decision record when docs claim behaviour ADRs still deny; update
   superseded paragraphs in 0018/0029/0032 rather than deleting history
3. **IMA / RRAO PUBLIC_API** — sync profiles and orchestration handoff symbols
4. **Thin package READMEs** — DRC-style expansion with doc tables
5. **Suite index** — refresh `docs/DOCUMENTATION_AUDIT.md`, root `CLAUDE.md` tree,
   missing `CLAUDE.md` (e.g. result-store)

Commit message pattern:

```text
docs: align package documentation with current runtime
```

Push branch `<agent>/doc-audit-fix` and open PR with:

- Summary of packages audited
- Bullet list of doc files changed
- Note: docs-only, no version bumps
- Residual follow-ups from audit

Run `make agent-guard` before commit (worktree should already exist from Step 1).

Do **not** run `make quality-control` unless the user requests it; doc-only PRs
typically skip calculation gates.

## References

- [`references/audit-checklist.md`](references/audit-checklist.md) — per-layer checks
- [`docs/DOCUMENTATION_AUDIT.md`](../../../docs/DOCUMENTATION_AUDIT.md) — last suite audit log
- [`docs/quality/package_maturity.toml`](../../../docs/quality/package_maturity.toml) — authoritative status
