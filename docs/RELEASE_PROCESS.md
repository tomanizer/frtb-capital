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

The material-change policy is defined in
[`docs/decisions/0005-material-change-policy.md`](decisions/0005-material-change-policy.md).
Material releases require the ADR, package-owner approval, model-validation
reviewer approval, changelog entry, and fixture review described there.

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

Release integrity is tracked through signed annotated tags where available,
GitHub artifact attestations, and checksum manifests. See
[`docs/REPO_CONTROLS.md`](REPO_CONTROLS.md) for the repository-control and
release-integrity policy.

## Release checklist

1. Confirm the working tree is clean on `main`.
2. Pull the latest `origin/main`.
3. Confirm all required GitHub checks passed on the merge commit.
4. Run local verification:

   ```bash
   uv sync --locked
   make check
   make build
   make audit-deps
   make sbom
   ```

5. In a `release/*` branch, for each package being released:
   a. Assemble changelog fragments and bump the version in one step:
      ```bash
      uv run towncrier build --package <pkg> --version <new-version> \
          --dir packages/<pkg>
      ```
      This writes the new `## [x.y.z]` section into `CHANGELOG.md`, removes
      the processed fragment files, and leaves `pyproject.toml` version
      unchanged — bump `version =` manually afterwards.
   b. Bump `version =` in `packages/<pkg>/pyproject.toml`.
   c. Regenerate the lock: `uv lock`.

   Open this as a `release/*` PR against `main`.  The CI version-bump and
   uv-lock guards are skipped on `release/*` branches.
6. Confirm material changes have an ADR, package-owner approval,
   model-validation approval, and fixture review where applicable.
7. Merge the release PR through the protected-branch workflow.
8. Create annotated tag(s) from the final `main` commit. Sign tags with the
   maintainer's configured GPG or SSH signing key where available.
9. Confirm `.github/workflows/release.yml` completed for the tag, or run it
   manually as a dry run before publishing release notes.
10. Confirm the release workflow uploaded:
   - source distributions and wheels under `dist/release/`,
   - `dist/sbom/frtb-capital.cdx.json`,
   - `dist/release/SHA256SUMS`,
   - `dist/release/release-checksums.json`,
   - GitHub artifact attestations for the release artifacts.
11. Capture repository-control evidence:

   ```bash
   make repo-controls-snapshot
   ```

12. Create a GitHub release that includes:
   - changelog excerpt,
   - affected packages and versions,
   - validation commands,
   - SBOM artifact from `dist/sbom/`,
   - release checksum manifest,
   - link to the GitHub artifact attestation.
13. Keep release notes factual. Do not describe outputs as final regulatory
    capital or production-approved unless independent validation has approved
    that status.

## SBOM

`make sbom` writes a CycloneDX JSON SBOM to:

```text
dist/sbom/frtb-capital.cdx.json
```

Attach this file to each suite release. For package-only releases, the suite
SBOM is still acceptable until package-specific SBOM generation is introduced.

## Release artifacts and attestations

`make release-artifacts` builds all workspace packages, generates the suite
SBOM, and writes SHA-256 checksum manifests:

```text
dist/release/
dist/release/SHA256SUMS
dist/release/release-checksums.json
dist/sbom/frtb-capital.cdx.json
```

The release workflow uses GitHub artifact attestations as the documented
attestation mechanism. It is intentionally dependency-free inside the Python
packages; provenance is an operational control owned by GitHub Actions, not by
the runtime calculators.
