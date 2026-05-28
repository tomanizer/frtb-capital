# Contributing to frtb-capital

This is a regulated-bank-software prototype suite. Contributions are reviewed against the standards in [`CLAUDE.md`](CLAUDE.md) and the audit checklist in [`docs/decisions/`](docs/decisions/).

## Setup

```bash
uv sync
make check
```

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

## Workflow

1. Open an issue or pick one labelled `audit-followup`, `enhancement`, or `bug`.
2. Branch from `main`.
3. Make the change in a single package where possible. Cross-package changes require an ADR.
4. Run `make check` until green.
5. Open a PR. The PR template will prompt for:
   - Affected package(s).
   - Whether the change is "material" under the policy below.
   - Link to ADR if material.

## Material change policy

A **material change** is one that:

- Alters a regulatory threshold value.
- Changes a calculation formula.
- Modifies the signature of any public API in a `frtb-*` package.
- Affects the numerical output of any committed golden fixture.
- Changes the `RegulatoryPolicy` schema.

Material changes **require**:

- An ADR in `docs/decisions/`.
- A version bump on the affected package.
- A `CHANGELOG.md` entry on that package.
- A regenerated fixture (if a fixture is affected) with a clean diff review.

Non-material changes (refactors with identical outputs, documentation, tests, performance optimisations) do not require an ADR but should still update CHANGELOG.

## Package discipline

- Sibling capital packages (`frtb-ima`, `frtb-sa`, `frtb-drc`, `frtb-cva`) must not import from each other.
- All shared types belong in `frtb-common`.
- The suite-level `frtb-orchestration` package is the only one allowed to import from multiple capital components.

## Commit messages

Use clear, imperative commit messages. The body should explain *why*. The summary should be ≤ 70 characters.

For commits authored by Codex, prefix the subject with `[codex]`. For commits authored or co-authored by Claude Code, include the Co-Authored-By trailer.

## Reviewing

Reviews follow the checklist in `CLAUDE.md`. Material changes require an additional reviewer with model-validation responsibilities.

## Releases

Release approvals, version tags, SBOM generation, and material-change release
rules are documented in [`docs/RELEASE_PROCESS.md`](docs/RELEASE_PROCESS.md).
