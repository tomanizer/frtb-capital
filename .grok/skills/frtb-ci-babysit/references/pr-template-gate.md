# PR template gate

Run after Step 0 and again before declaring merge-ready. Read the PR body:

```bash
gh pr view $PR --json body,headRefName -q .body > /tmp/pr-body-$PR.md
```

## Always required

- **Summary** has substantive bullets (not empty) for non-trivial PRs.
- **Affected packages** checkboxes match packages touched in the diff (`packages/<name>/`).

## Issue closing (ADR / CONTRIBUTING)

If the PR completes tracked work, the body must include explicit lines:

```text
Closes #123
```

GitHub does not close issues from parent-issue checkboxes alone. Missing `Closes #N`
is a **merge blocker** when the PR title or summary claims to fix issues.

## Non-release branch (`headRefName` does not start with `release/`)

- No `version =` bumps in `packages/*/pyproject.toml`.
- No new release sections in `packages/*/CHANGELOG.md` (use `packages/*/changelog.d/*.md`
  fragments per ADR 0015).
- `uv.lock` only with dependency-spec changes (CI `uv-lock-guard`).

## Public API / wrappers

If the diff touches `packages/*/src/**/__init__.py`, public entrypoints, or adds
adapter/wrapper modules:

- Public API section filled with changed symbols.
- Wrapper section completed or “does not add wrappers” checked truthfully.

## Material changes

If numerical outputs, regulatory thresholds, or public API semantics change:

- Material Change section links an ADR in `docs/decisions/` or explains why ADR 0005
  does not apply (rare; must be specific).

## Docs-only PRs

Link to verification: `make docs-check` (babysitter runs locally or cites green `docs` CI).