---
description: Babysit an frtb-capital PR from push to merge-ready. Monitors CI, waits for and incorporates the automated Gemini review, marks the PR ready for review to trigger Copilot, incorporates Copilot feedback, then runs a final subagent audit. Use when asked to babysit, watch, or fix a frtb-capital PR.
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
| Default | Babysit PR for current branch |

## Execution rules

1. Run `python3 scripts/agent_worktree.py guard` before edits. On failure:
   `make agent-new AGENT=claude TASK=ci-babysit`.
2. Complete Phases 0 → 1 → 2 → 3 → 4 in order.
3. **Skip unavailable reviewers:** Copilot credit/quota messages → skip Phase 3.
   Gemini blocked/quota/timeout → skip Gemini; run fallback reviews (`cursor review`,
   then non-author PR comment review) per the skill; skip if all fail.
4. Use the **current** CI job table in the skill (PRs do not run `test (3.12)` /
   `test (3.13)`).
5. Deliver the final output section from the skill (include PHASE2_STATUS and
   COPILOT_STATUS) before stopping.

Do not invent a shorter babysit flow.