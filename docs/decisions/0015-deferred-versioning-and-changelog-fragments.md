# ADR 0015 — Deferred versioning and changelog fragments

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-05-30 |
| Supersedes | ADR 0005 §4-5 (version bump and changelog requirements for PRs) |
| Affected packages | All workspace packages |

## Context

Every feature PR that triggers a material-change version bump under ADR 0005
touches three shared files: `packages/<pkg>/pyproject.toml` (version field),
`packages/<pkg>/CHANGELOG.md` (new release section), and `uv.lock` (which
records every workspace member's version and is regenerated automatically by
`uv sync`). Any two concurrent PRs touching the same package therefore produce
merge conflicts in all three files on every rebase or update — even when the
code changes themselves are orthogonal.

This is not a tooling failure; it is a policy collision. ADR 0005 requires the
version bump and changelog entry to land in the same PR as the material change.
That constraint, combined with per-package independent versioning and a
high-cadence automated coding workflow (Codex / Claude Code), turns every
parallel PR into a guaranteed conflict.

## Decision

### 1. Feature PRs do not carry version numbers or release sections

Feature and bug-fix PRs (any branch that does not match `release/*`) must not
change:

- the `version =` field in any `packages/*/pyproject.toml`,
- an existing `## [x.y.z]` release section header in any `CHANGELOG.md`,
- `uv.lock` unless the PR's own dependency specifications change (i.e. the
  `[project] dependencies` or `[dependency-groups]` sections of a
  `pyproject.toml` are modified).

CI enforces these constraints with two guard jobs (see §4).

ADR 0005 §4–5 is superseded for the *timing* of version bumps and changelog
entries. The requirement that material changes have a version bump and changelog
entry is retained; only the location in the workflow changes.

### 2. Feature PRs carry changelog fragments

Each feature or fix PR that has a user-visible change adds one or more
**towncrier fragment files** under `packages/<pkg>/changelog.d/`. Fragment
filenames follow the pattern:

```
<issue-or-pr-number>.<type>.md
```

Allowed types: `fix`, `feat`, `chore`, `security`, `breaking`, `docs`.

Fragment content: a single sentence or short paragraph describing the change
from a consumer's perspective. Do not include version numbers.

Example for PR #181 fixing an SBM parameter:

```
packages/frtb-sbm/changelog.d/181.fix.md
```

```
Fix cap sentinel handling in `apply_correlation_scenario_definition` to
distinguish an explicit `cap=0.0` from an absent cap (MAR21.6).
```

CI does **not** enforce fragment presence — some PRs (pure CI fixes, docs,
dependency bumps) legitimately have no fragment. Fragment absence is acceptable;
a fragment for a non-user-visible change is also acceptable and encouraged.

### 3. Release PRs assemble fragments and assign version numbers

A release PR is any PR from a branch matching `release/*`. It:

1. Runs `towncrier build --package <pkg> --version <new-version>` for each
   package being released, which assembles fragments into a new `## [x.y.z]`
   section at the top of `CHANGELOG.md` and removes the processed fragment
   files.
2. Bumps `version =` in the relevant `packages/*/pyproject.toml` files.
3. Runs `uv lock` to regenerate `uv.lock` with updated versions.
4. Opens the release PR against `main`; CI guards on `release/*` branches
   permit version changes and uv.lock changes.

A release PR that conflicts is a sign of two concurrent release PRs — a
configuration that should be avoided by serialising releases.

### 4. CI guard jobs

Two new jobs in `.github/workflows/ci.yml`:

**`version-bump-guard`** — runs on PRs from non-`release/*` branches. Fails if
any `packages/*/pyproject.toml` `version =` line changed relative to `main`.

**`uv-lock-guard`** — runs on all PRs. Fails if `uv.lock` changed but neither
`pyproject.toml` nor any `packages/*/pyproject.toml` dependency-specification
section (`[project] dependencies`, `[dependency-groups]`, `[tool.uv.sources]`)
changed.

Both guards are skipped on `release/*` branches (where version bumps and
lock regeneration are expected) and on `main`/`schedule` events.

### 5. How this interacts with ADR 0005

ADR 0005 §1–3 and §6–7 are unchanged. The material-change classification,
approval chain, ADR requirement, fixture review, and traceability requirements
all remain.

For §4 (version bump): the bump is still required for a material change; it now
lands in the release PR rather than the feature PR. The feature PR records the
*intent* via a changelog fragment.

For §5 (changelog entry): the entry is now written as a fragment in the feature
PR and assembled into `CHANGELOG.md` in the release PR.

## Alternatives considered

**Merge queue (GitHub)** — serialises merges so only one PR regenerates
`uv.lock` at a time. This eliminates uv.lock conflicts but not version/changelog
conflicts. It is a complementary control, not a substitute for this policy. It
requires branch-protection configuration changes (repository settings, not
committed code) and should be enabled separately.

**Single shared CHANGELOG at workspace root** — reduces the number of
conflicting files but does not eliminate version-number conflicts. The
per-package changelog structure is load-bearing for independent package
versioning and is retained.

**Release-please bot** — fully automates versioning and changelog assembly via
PR labels and Conventional Commits. Viable long-term; deferred because it
requires Conventional Commit discipline across all agent-generated commits and
introduces a GitHub App dependency. This ADR's fragment approach is compatible
with a future migration to release-please.

## Consequences

- Feature PRs become conflict-free on the three shared files in almost all
  cases. The exception is two PRs that simultaneously add a fragment with the
  same filename (same PR number is impossible; a collision is a naming error).
- Release PRs are now slightly larger (they do the versioning work) but there
  is typically one release PR per package per release cycle, not one per
  feature.
- Agents (Codex, Claude Code) must not bump versions or edit CHANGELOG release
  sections in feature PRs. The babysit skill and agent instructions should be
  updated accordingly.
- `uv.lock` in feature PRs is now only touched when dependencies genuinely
  change, which reduces its noise in code review.
