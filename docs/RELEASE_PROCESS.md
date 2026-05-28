# Release process

This document defines how releases are cut for the `frtb-capital` suite. It is
governance documentation for a prototype capital-calculation workspace; it does
not make the software approved for regulatory reporting.

## Release triggers

Cut a release when one of these conditions is met:

- A package change is ready for external use or validation review.
- A material model change lands and needs an immutable version reference.
- A security fix or dependency remediation must be distributed.
- A documentation or governance baseline needs a stable tag for audit evidence.

Do not cut releases from feature branches. Releases are cut from `main` after
the protected-branch workflow has completed.

## Approval

Every release needs approval from:

- The engineering maintainer for build, CI, packaging, and dependency hygiene.
- The package owner for each package whose version changes.
- A model-validation reviewer for any material model change.
- A security reviewer for vulnerability or supply-chain releases.

The material-change policy is currently defined in
[`CONTRIBUTING.md`](../CONTRIBUTING.md). Audit follow-up
[`#16`](https://github.com/tomanizer/frtb-capital/issues/16) will move that
policy into an ADR and expand the change-control workflow.

## Versioning

The workspace and each package use Semantic Versioning:

- `MAJOR`: incompatible public API change, regulatory methodology change, or
  validated model boundary change.
- `MINOR`: backward-compatible feature, new package capability, or new
  audit/reporting artifact.
- `PATCH`: backward-compatible bug fix, documentation fix, CI fix, or
  dependency/security remediation with unchanged model outputs.

Before production validation is complete, versions remain in the `0.y.z` range.
Within `0.y.z`, any material model change must still be treated as release
significant and must have an ADR, changelog entry, and reviewer approval.

Package versions are independent. Bump only packages affected by a change. Use
the root workspace version for suite-level tooling and coordinated releases.

## Tagging

Use annotated tags:

- Suite release: `suite-vX.Y.Z`
- Package release: `<package-name>-vX.Y.Z`, for example `frtb-ima-v0.1.1`

For a coordinated suite release, create both the suite tag and any package tags
that changed. Each tag message should include:

- Release title.
- Commit SHA on `main`.
- Changed package versions.
- Link to the GitHub release notes or PR.

Release signing is intentionally not defined here. Signed releases are tracked
as a separate supply-chain follow-up.

## Release checklist

1. Confirm the working tree is clean on `main`.
2. Pull the latest `origin/main`.
3. Confirm all required GitHub checks passed on the merge commit.
4. Run local verification:

   ```bash
   uv sync --locked
   make check
   make audit-deps
   make sbom
   ```

5. Update affected package versions and changelogs in a release PR.
6. Confirm material changes have an ADR and model-validation approval.
7. Merge the release PR through the protected-branch workflow.
8. Create annotated tag(s) from the final `main` commit.
9. Create a GitHub release that includes:
   - changelog excerpt,
   - affected packages and versions,
   - validation commands,
   - SBOM artifact from `dist/sbom/`.
10. Keep release notes factual. Do not describe outputs as final regulatory
    capital or production-approved unless independent validation has approved
    that status.

## SBOM

`make sbom` writes a CycloneDX JSON SBOM to:

```text
dist/sbom/frtb-capital.cdx.json
```

Attach this file to each suite release. For package-only releases, the suite
SBOM is still acceptable until package-specific SBOM generation is introduced.
