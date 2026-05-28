# Contributing to frtb-capital

This is a regulated-bank-software prototype suite. Contributions are reviewed
against the standards in [`CLAUDE.md`](CLAUDE.md), the package-specific agent
guidance, and the ADR log in [`docs/decisions/`](docs/decisions/).

## Setup

```bash
uv sync
make check
```

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

## Workflow

1. Open an issue or pick one labelled `audit-followup`, `enhancement`, or `bug`.
2. Branch from `main`.
3. Make the change in a single package where possible. Cross-package model
   changes require an ADR.
4. Run `make check` until green.
5. Open a PR. The PR template will prompt for:
   - Affected package(s).
   - Whether the change is material under
     [ADR 0005](docs/decisions/0005-material-change-policy.md).
   - Link to ADR if material.

## Material change policy

The canonical material-change policy is
[`docs/decisions/0005-material-change-policy.md`](docs/decisions/0005-material-change-policy.md).

In short, material changes include regulatory threshold changes, calculation
formula or input-routing changes, `RegulatoryPolicy` or public API semantic
changes, fixture numerical output changes, requirement-status changes, package
boundary changes, audit-record semantic changes, and model-version or release
semantics changes.

Material changes require an ADR, package-owner approval, model-validation
reviewer approval, affected package version bump, changelog entry, and fixture
review when fixture outputs or hashes change.

Non-material changes include refactors with identical outputs, documentation
changes that do not reinterpret regulatory treatment, test additions,
performance optimisations with identical outputs, and CI/formatting changes.
They do not require an ADR but should still update changelogs when useful for
release notes.

## Package discipline

- Sibling capital packages (`frtb-ima`, `frtb-sa`, `frtb-drc`, `frtb-cva`) must not import from each other.
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
