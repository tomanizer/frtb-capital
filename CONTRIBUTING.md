# Contributing to frtb-capital

This is a regulated-bank-software prototype suite. Contributions are reviewed
against the standards in [`CLAUDE.md`](CLAUDE.md), the package-specific agent
guidance, and the ADR log in [`docs/decisions/`](docs/decisions/).

## Setup

```bash
uv sync --locked
make check
```

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). The repo pins
3.11 in .python-version so local runs match CI (test (3.11)) automatically.

## Workflow

1. Open an issue or pick one labelled `audit-followup`, `enhancement`, or `bug`.
2. Branch from `main` (not from `release/*`).
3. Make the change in a single package where possible. Cross-package model
   changes require an ADR.
4. Run `make check` until green.
5. For larger code changes, run `make drift-check`, `make changed-code-check`,
   `make test-value-check`, and `make dead-code-check` before committing. If the
   branch intentionally increases the code-drift baseline, run
   `make drift-baseline` and include that baseline diff for review.
6. Add a changelog fragment if the change is user-visible (see below).
7. Open a PR. The PR template will prompt for:
   - Affected package(s).
   - Whether the change is material under
     [ADR 0005](docs/decisions/0005-material-change-policy.md).
   - Link to ADR if material.

### Closing issues via PR

GitHub only closes issues that are explicitly named in the PR body with
`Closes #N` (or `Fixes #N`, `Resolves #N`). Checkboxes inside a parent issue
body (`- [x] #N`) are not followed automatically.

**Rule:** when a PR closes a parent/phase issue that contains checked
sub-issues, every closed sub-issue must also appear as an explicit `Closes #N`
line in the PR body.

```
Closes #187, #188, #189, #190, #191, #192, #193, #194
Closes #195, #196, #197, #198, #199
Closes #214
```

As a safety net, the `cascade-close-subissues` GitHub Action will
automatically close any checked `- [x] #N` sub-issues when the parent issue is
closed. The explicit `Closes #N` lines in the PR body are still preferred
because they appear in the merge event audit trail and create a visible link on
each child issue.

### What not to do in a feature PR

Per [ADR 0015](docs/decisions/0015-deferred-versioning-and-changelog-fragments.md),
feature and fix PRs **must not**:

- Bump `version =` in any `packages/*/pyproject.toml`.
- Add a `## [x.y.z]` release section to any `CHANGELOG.md`.
- Regenerate `uv.lock` unless the PR itself changes dependency specifications.

CI will reject PRs that violate these constraints. Version bumps and changelog
assembly happen in a dedicated `release/*` PR (see
[Release process](docs/RELEASE_PROCESS.md)).

### Changelog fragments

Each user-visible change should add a fragment file under
`packages/<pkg>/changelog.d/`. The filename is `<pr-number>.<type>.md`.

Allowed types: `fix`, `feat`, `breaking`, `security`, `chore`, `docs`.

```
# Example: packages/frtb-sbm/changelog.d/181.fix.md
Fix cap sentinel handling in `apply_correlation_scenario_definition` to
distinguish an explicit `cap=0.0` from an absent cap (MAR21.6).
```

Fragment content is a single sentence or short paragraph from a consumer's
perspective. Do not include version numbers. Pure CI/tooling/docs PRs with no
consumer-visible impact do not need a fragment.

## Material change policy

The canonical material-change policy is
[`docs/decisions/0005-material-change-policy.md`](docs/decisions/0005-material-change-policy.md).

In short, material changes include regulatory threshold changes, calculation
formula or input-routing changes, `RegulatoryPolicy` or public API semantic
changes, fixture numerical output changes, requirement-status changes, package
boundary changes, audit-record semantic changes, and model-version or release
semantics changes.

Material changes require an ADR, package-owner approval, model-validation
reviewer approval, a changelog fragment (per ADR 0015, the version bump and
final changelog entry are assembled in the release PR), and fixture review when
fixture outputs or hashes change.

Non-material changes include refactors with identical outputs, documentation
changes that do not reinterpret regulatory treatment, test additions,
performance optimisations with identical outputs, and CI/formatting changes.
They do not require an ADR; a changelog fragment is optional but encouraged.

## Package discipline

- Sibling capital packages (`frtb-ima`, `frtb-sbm`, `frtb-drc`, `frtb-rrao`, `frtb-cva`) must not import from each other.
- All shared types belong in `frtb-common`.
- The suite-level `frtb-orchestration` package is the only one allowed to import from multiple capital components.

## Commit messages

Use clear, imperative commit messages. The body should explain *why*. The summary should be ≤ 70 characters.

For commits authored by Codex, prefix the subject with `[codex]`. For commits authored or co-authored by Claude Code, include the Co-Authored-By trailer.

## Reviewing

Reviews follow the checklist in `CLAUDE.md`. Material changes require an
additional reviewer with model-validation responsibilities before merge.

## Releases

Release approvals, version tags, SBOM generation, and material-change release
rules are documented in [`docs/RELEASE_PROCESS.md`](docs/RELEASE_PROCESS.md).
