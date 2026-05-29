# Agent Worktree Policy

This repository has one protected main clone and one standard worktree root:

- Protected main clone: `~/Documents/Projects/frtb-capital`
- Agent worktree root: `~/Documents/Projects/frtb-capital-worktrees`

The protected main clone is for syncing `main` with `origin/main`, reading, and
creating new worktrees. Do not edit, commit, or switch branches in that clone.

Normal agent work must happen in:

```text
~/Documents/Projects/frtb-capital-worktrees/<agent>/<task>
```

The branch name must start with the same `<agent>` component:

```text
codex/drc-scenarios
claude/review-pr-72
cursor/sbm-ui-copy
copilot/cva-tests
grok/rrao-doc-pass
```

## Required Workflow

1. Sync the protected main clone:

   ```bash
   make agent-sync-main
   ```

2. Create a worktree from `origin/main`:

   ```bash
   make agent-new AGENT=codex TASK=drc-scenarios
   ```

3. Work only inside the printed worktree path.

4. Run the guard before editing if there is any doubt:

   ```bash
   make agent-guard
   ```

5. List known worktrees:

   ```bash
   make agent-worktrees
   ```

## Guardrails

Repo-managed Git hooks live in `.githooks/`. Install them once per local clone:

```bash
make agent-setup
```

The hooks block commits and pushes when:

- the current path is the protected main clone;
- the current branch is `main`;
- the worktree is outside `~/Documents/Projects/frtb-capital-worktrees`;
- the first branch component does not match the first worktree path component;
- a push targets `refs/heads/main`.

The hooks cannot prevent an editor from modifying files in the protected main
clone before Git is invoked. Agents must still run the guard before changing
files and must move to a proper worktree if the guard fails.

## Exceptions

One-off review work may inspect another branch or PR, but it must not modify the
protected main clone. If review work needs edits, create a dedicated review
worktree under the standard root, for example:

```bash
make agent-new AGENT=codex TASK=review-pr-72
```

Then fetch or check out the reviewed branch from inside that worktree.
