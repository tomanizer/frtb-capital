---
description: Babysit an frtb-capital PR from push to merge-ready. Monitors CI, gates PR template, resolves review threads, incorporates bot reviews when available, final subagent audit.
allowed-tools: Bash, Read, Edit, Write, Agent
---

# FRTB CI babysit

Execute the shared PR babysit workflow. The canonical procedure is **not** duplicated
here — read and follow it in full:

1. `.grok/skills/frtb-ci-babysit/SKILL.md`
2. `.grok/skills/frtb-capital/SKILL.md` (workspace rules)
3. `AGENTS.md` and `docs/AGENT_WORKTREE_POLICY.md`

## Arguments

Pass through to the skill:

| User text | Skill handling |
| --- | --- |
| PR number (e.g. `534`) | Set `PR` and `gh pr checkout` if not on that branch |
| `agent codex` / `for copilot` | Use `--agent <name>` when creating a worktree |
| `ci only` / `skip reviews` / `reviews only` | `--ci-only`, `--skip-reviews`, `--reviews-only` |
| Default | Babysit PR for current branch |

## Execution rules

1. Run `python3 scripts/agent_worktree.py guard` before edits. On failure:
   `make agent-new AGENT=claude TASK=ci-babysit`.
2. Complete Steps 0 → 0.5 → 0.6 → Phases 1 → 2 → 3 → **3.5** → 4 unless mode flags skip phases.
3. **Consider and resolve all PR review threads** per `references/conversations.md` (Phase 3.5).
4. **Skip unavailable reviewers:** Copilot credits → skip Phase 3. Gemini blocked/timeout →
   fallbacks (`@cursoragent review`, then non-author review); skip if all fail.
5. Pin `HEAD_SHA`; after each push re-run Phase 1 when SHA changes (max 3 fix loops per phase).
6. Use `classify_changed_paths` + `references/ci-job-matrix.md` for required jobs and docs-only fast path.
7. Deliver the final output section from the skill before stopping.

Do not invent a shorter babysit flow.