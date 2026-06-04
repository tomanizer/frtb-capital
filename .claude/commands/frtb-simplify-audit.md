---
description: Audit frtb-capital source for maintainability (complexity, wrappers, duplication). Produces per-package reports and optional tracking issues/PR.
allowed-tools: Bash, Read, Grep, Glob, Edit, Write, Agent
---

# FRTB simplification audit

Read and execute:

1. `.grok/skills/frtb-simplify-audit/SKILL.md`
2. `.grok/skills/frtb-simplify-audit/references/audit-checklist.md`
3. `docs/quality/simplification/rubric.md`

## Arguments

| User text | Flags |
| --- | --- |
| report only / no issues | `--report-only` |
| create issues + PR | `--issues` |
| `agent codex` | `--agent codex` |

Default: `--report-only` unless user asked for issues/PR.

## Rules

1. `python3 scripts/agent_worktree.py guard` before edits; `make agent-new AGENT=claude TASK=simplify-audit` on failure.
2. Audit packages in skill order; do not refactor runtime code unless user explicitly requests implementation.
3. Deliver suite `README.md` path before opening a governance PR.
