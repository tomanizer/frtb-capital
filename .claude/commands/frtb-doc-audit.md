---
description: Audit frtb-capital package documentation against code and maturity registry; optional doc-fix PR. Use when asked for a documentation audit, stale docs check, or doc alignment across packages.
allowed-tools: Bash, Read, Grep, Glob, Edit, Write, Agent
---

# FRTB documentation audit

Execute the shared documentation audit workflow for this repository. The
canonical procedure lives in Grok project skills and applies to Claude Code,
Codex, Cursor, and Copilot via the same files.

## Required reading

Read these files in full before any edits:

1. `.grok/skills/frtb-doc-audit/SKILL.md`
2. `.grok/skills/frtb-doc-audit/references/audit-checklist.md`
3. `.grok/skills/frtb-capital/SKILL.md` (workspace rules reminder)
4. `AGENTS.md` and `docs/AGENT_WORKTREE_POLICY.md` (worktree policy)

## Arguments

Interpret the user's command text after `/frtb-doc-audit`:

| User intent | Skill flags |
| --- | --- |
| Default or "audit and fix" | `--fix` |
| "report only" / "no PR" / "audit only" | `--report-only` |
| `agent codex` / `for copilot` | `--agent <name>` on worktree creation |

Pass these flags through to the skill steps; do not invent a different workflow.

## Execution rules

1. Run `python3 scripts/agent_worktree.py guard`. On failure, run
   `make agent-new AGENT=claude TASK=doc-audit-fix` from the protected main
   clone and continue in the new worktree.
2. Follow every numbered step in `.grok/skills/frtb-doc-audit/SKILL.md`.
3. Deliver the structured audit report from Step 5 before opening a PR.
4. If `--report-only`, stop after the report.
5. Documentation-only PRs: no package version bumps (ADR 0015).

Do not skip the per-package pass or the cross-cutting stale-doc grep in the
checklist reference.