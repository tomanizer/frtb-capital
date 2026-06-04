# Agent Worktree Policy

This repository has one protected main clone and one standard worktree root.
Both paths are local-machine policy, not repository constants:

- Protected main clone: the local checkout that owns the `main` worktree.
- Agent worktree root: by default, a sibling directory named
  `<protected-main-dir>-worktrees`.

The protected main clone is for syncing `main` with `origin/main`, reading, and
creating new worktrees. Do not edit, commit, or switch branches in that clone.

Normal agent work must happen in:

```text
<worktree-root>/<agent>/<task>
```

The branch name must start with the same `<agent>` component:

```text
codex/drc-scenarios
claude/review-pr-72
cursor/sbm-ui-copy
copilot/cva-tests
grok/rrao-doc-pass
```

## Local Path Resolution

`scripts/agent_worktree.py` resolves paths in this order:

1. explicit `--main-clone` / `--worktree-root` command-line flags;
2. `FRTB_AGENT_MAIN_CLONE` / `FRTB_AGENT_WORKTREE_ROOT`;
3. repo-local Git config `frtb.agentMainClone` / `frtb.agentWorktreeRoot`;
4. Git worktree auto-discovery for the `main` worktree, with a sibling
   `<protected-main-dir>-worktrees` root.

For example, on a machine where the protected clone lives outside a synced
folder, either rely on auto-discovery or set the local configuration
explicitly:

```bash
git config --local frtb.agentMainClone <protected-main-clone>
git config --local frtb.agentWorktreeRoot <standard-worktree-root>
```

These settings are stored in the local Git config and must not be committed.

## Required Workflow

1. Sync the protected main clone:

   ```bash
   make agent-sync-main
   ```

2. Before any file edit, ensure a compliant agent worktree (from **any** clone,
   including the protected main clone):

   ```bash
   make agent-ensure AGENT=codex TASK=drc-scenarios
   ```

   - If already in `<worktree-root>/codex/drc-scenarios` on branch `codex/drc-scenarios`,
     the command succeeds in place.
   - Otherwise it creates the worktree (after `sync-main`) or tells you to reuse
     an existing one and prints `next: cd ...`. **Agents must `cd` there before
     editing.**

3. Work only inside that worktree path for commits and pushes.

4. Optional checks:

   ```bash
   make agent-guard    # verify only; does not create a worktree
   make agent-worktrees
   ```

`make agent-new` remains available when you explicitly want a fresh worktree
without the ensure helper.

## Guardrails

Repo-managed Git hooks live in `.githooks/`. Install them once per local clone:

```bash
make agent-setup
```

The hooks block commits and pushes when:

- the current path is the protected main clone;
- the current branch is `main`;
- the worktree is outside the resolved standard worktree root;
- the first branch component does not match the first worktree path component;
- the branch fails the changed-code complexity check enforced by
  `scripts/ci/check_code_drift.py --changed`;
- a push targets `refs/heads/main`.

During drift-control calibration, `pre-push` runs the broader drift,
test-value, and dead-code guards as report-only warnings. `make agent-guard`
does not require hooks to be installed; `make agent-doctor` reports missing
hooks so contributors can run `make agent-setup`.

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
