# Dependency audit and SBOM scope

This note documents what the suite's dependency-security tooling covers and how
SBOM artifacts are produced in local workflows and CI.

## `make audit-deps` (pip-audit)

`make audit-deps` runs [`pip-audit`](https://pypi.org/project/pip-audit/) against
the active workspace virtual environment (`.venv`). It reports known
vulnerabilities in **third-party packages installed from PyPI or other remote
indexes**.

What it covers:

- Runtime and development dependencies resolved into `.venv` by `uv sync`.
- Published vulnerability advisories matched to installed package names and
  versions.

What it does **not** cover:

- First-party workspace packages (`frtb-ima`, `frtb-rrao`, and siblings). These
  are local editable installs, not PyPI distributions, so pip-audit correctly
  skips them.
- Custom or proprietary code quality, model validation, or regulatory
  correctness. Those remain package tests, maturity checks, and independent
  review responsibilities.
- Transitive packages that are present only as build metadata and not installed
  into `.venv`.

CI runs `make audit-deps` on pull requests when `pyproject.toml` or `uv.lock`
changes. A clean result means no known advisories were found for auditable
third-party packages in the lockfile-resolved environment.

## `make sbom` (CycloneDX)

`make sbom` generates `dist/sbom/frtb-capital.cdx.json`, a CycloneDX JSON SBOM
for the `.venv` environment using `cyclonedx-py`. The artifact lists installed
third-party components and versions at generation time.

CI runs the same target in the `sbom` job and uploads the artifact for release
workflows. Release packaging (`make checksums`) includes the SBOM path in the
checksum manifest when present.

## Local workflow

```bash
uv sync
make audit-deps
make sbom
make checksums   # optional: ties release wheels to SBOM metadata
```

For mutation-testing artifact checks, see
[`mutation_baseline.md`](frtb-ima/mutation_baseline.md) and
[`docs/quality/coverage_policy.md`](coverage_policy.md).

## Interpreting results

| Command | Pass meaning | Does not prove |
| --- | --- | --- |
| `make audit-deps` | No known CVEs in installed third-party packages | Safe or correct first-party calculation code |
| `make sbom` | SBOM file generated successfully | That every dependency is approved for production use |
| `make quality-control` | Import boundaries and maturity evidence satisfied | Regulatory capital completeness |

Treat these controls as complementary: dependency audit and SBOM generation
address supply-chain visibility for third-party packages; suite quality-control
and package tests address calculation correctness and governance.
