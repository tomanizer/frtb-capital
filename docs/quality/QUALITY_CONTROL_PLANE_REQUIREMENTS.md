# frtb-capital quality control plane requirements

## Scope of this document

This document specifies the **first implementation PR** for the quality control
plane. It is not the full plane design. It covers only what must land in a
single reviewable PR: a package maturity registry, an import smoke check, a
maturity evidence check, Make targets, a CI job, and unit tests.

Follow-on controls — regulatory scanner, diff-sensitive evidence routing, AI
advisory review, reusable agent skills — are listed in
[Follow-on controls](#follow-on-controls) with explicit phases, dependencies,
and definitions of done. That section is a stub roadmap, not a wish list. Each
phase requires its own spec before implementation begins.

---

## Current repo facts

The requirements below are based on `origin/main` after PR #130:

- all workspace packages import successfully when the locked workspace is
  synced;
- `frtb-ima` has implemented IMA evidence and model documentation;
- `frtb-rrao` is marked `IMPLEMENTED` / `AVAILABLE` in package metadata and has
  RRAO v1 evidence;
- `frtb-drc` has a partial non-securitisation runtime path and is marked
  `PARTIAL` / `PENDING`;
- `frtb-sbm` and `frtb-cva` are scaffolded packages that intentionally fail
  calculation entry points;
- `frtb-orchestration` is a partial suite-level aggregation boundary, not a full
  model package;
- `frtb-common` is a shared library, not a capital component.

---

## Scope of the first PR

The first PR must add:

1. a package maturity registry (`docs/quality/package_maturity.toml`);
2. a registry loader and validation primitives;
3. an import smoke check script;
4. a package maturity/evidence check script;
5. Make targets for local and CI execution;
6. a `quality-control` CI job that is never skipped;
7. an update to `docs/REPO_CONTROLS.md` adding `quality-control` to the
   required-checks table;
8. unit tests for the registry loader and all check behaviors;
9. root pytest discovery for the new quality-control tests;
10. an IMA package metadata object so all implemented capital packages expose
   the same status contract;
11. only the minimum missing DRC evidence files required for the `partial_runtime`
   gate — see [DRC evidence pre-check](#drc-evidence-pre-check) below.

The first PR must not add:

- AI review as a required merge blocker;
- regulatory banned-language scanning;
- PR-template enforcement;
- diff-sensitive change-classifier evidence gates;
- broad model-documentation skeletons that only exist to satisfy the checker.

---

## Maturity profiles

The maturity registry must use these profile names:

| Profile | Packages | Meaning |
| --- | --- | --- |
| `implemented` | `frtb-ima`, `frtb-rrao` | Executable capital component with model evidence and validation artifacts. |
| `partial_runtime` | `frtb-drc` | Executable partial component with explicit unsupported boundaries. |
| `scaffolded` | `frtb-sbm`, `frtb-cva` | Importable package with intentional not-implemented calculation boundary. |
| `orchestration_partial` | `frtb-orchestration` | Suite coordination package with partial aggregation contracts. |
| `shared` | `frtb-common` | Shared library used by capital packages. |

The checker must fail for unknown profile names. Profile names must be stable
because CI, docs, and future agent instructions will refer to them.

---

## Registry format

Use `docs/quality/package_maturity.toml` so the checker can parse it with the
Python 3.11 standard library `tomllib`. Do not add a PyYAML dependency for the
first PR.

Required shape:

```toml
schema_version = 1

[[packages]]
package = "frtb-rrao"
import_name = "frtb_rrao"
path = "packages/frtb-rrao"
module_docs = "docs/modules/frtb-rrao"
maturity = "implemented"
component_type = "capital"
metadata_object = "frtb_rrao.scaffold:PACKAGE_METADATA"
calculation_entrypoint = "frtb_rrao:calculate_rrao_capital"

[[packages.required_tests]]
id = "public-api"
path = "packages/frtb-rrao/tests/test_public_api.py"
```

Required fields for every package:

- `package`: distribution/package directory name;
- `import_name`: Python import root;
- `path`: package root;
- `module_docs`: module documentation root, where applicable;
- `maturity`: one of the supported profile names;
- `component_type`: `capital`, `orchestration`, or `shared`.

Optional fields:

- `metadata_object`: import path to package metadata, required for capital and
  orchestration packages;
- `calculation_entrypoint`: import path to public calculation boundary, required
  for capital and orchestration packages;
- `required_tests`: package-local test evidence entries, used when a profile
  requires a specific behavior to be covered by tests;
- `notes`: short explanatory text for intentional deviations.

Each `required_tests` entry must have:

- `id`: stable evidence id, unique within the package;
- `path`: repository-relative path to an existing `test_*.py` file under the
  package's tests directory. The root `tests/quality/` path is only valid for
  the quality-control scripts' own registry entry, not for capital, shared, or
  orchestration package entries.

Registry validation requirements:

- package names must be unique;
- import names must be unique;
- paths must exist;
- registry package names must match the directory names under `packages/`;
- every package directory under `packages/` must appear exactly once in the
  registry;
- `metadata_object`, when provided, must import successfully;
- `calculation_entrypoint`, when provided, must import successfully;
- every `required_tests` path must exist and every `required_tests.id` must be
  unique within its package.

The initial registry must include this IMA entry so IMA participates in the same
metadata and entry-point contract as RRAO:

```toml
[[packages]]
package = "frtb-ima"
import_name = "frtb_ima"
path = "packages/frtb-ima"
module_docs = "docs/modules/frtb-ima"
maturity = "implemented"
component_type = "capital"
metadata_object = "frtb_ima:PACKAGE_METADATA"
calculation_entrypoint = "frtb_ima:models_based_capital_for_policy"
```

The first PR must add `PACKAGE_METADATA` for IMA with:

- `package_name = "frtb-ima"`;
- `import_name = "frtb_ima"`;
- `implementation_status = ImplementationStatus.IMPLEMENTED`;
- `validation_status = ValidationStatus.AVAILABLE`.

Define the object in the IMA package and export it from `frtb_ima` so the
registry path above imports without reaching into a private module.

> **Implementer note:** verify that `frtb_ima:models_based_capital_for_policy`
> is the actual public name exported from `frtb_ima/__init__.py` before
> committing the registry entry. The checker validates this import on every
> `make quality-control` run, so a wrong name fails the gate on day one.

### Registry governance

Automated governance for status flips, signed commits, and CODEOWNERS
restriction on the TOML file is deliberately deferred. Existing material-change
governance is not deferred: ADR 0005 still applies when a maturity change also
changes model boundaries, requirement status, validation claims, release
semantics, or other material model evidence. This is a recorded decision about
tooling scope, not an exemption from the repository's accepted ADR policy.

Until automated governance controls are in place, any PR that flips a package
maturity status must include a human reviewer approval and a changelog entry
stating what evidence justified the promotion. If ADR 0005 classifies the change
as material, the PR must also link the required ADR.

---

## Import smoke check

Add `scripts/ci/import_smoke.py` and `make import-smoke`.

The check must import exactly these import roots from the registry:

- `frtb_common`;
- `frtb_ima`;
- `frtb_sbm`;
- `frtb_drc`;
- `frtb_rrao`;
- `frtb_cva`;
- `frtb_orchestration`.

Failure output must name every failed import and include the exception class and
message. The script must return non-zero if any import fails.

The import smoke check must have a fixture-based unit test that proves a missing
or invalid import is reported clearly.

---

## Package maturity check

Add `scripts/ci/check_package_maturity.py` and `make maturity-check`.

The checker must support:

```bash
uv run python scripts/ci/check_package_maturity.py
uv run python scripts/ci/check_package_maturity.py --package frtb-rrao
uv run python scripts/ci/check_package_maturity.py --json-output dist/quality/package-maturity.json
```

Default behavior checks all packages. `--package` checks one registry entry and
fails for unknown package names.

JSON output must include package-level pass/fail status and failed requirement
ids. The JSON output is diagnostic evidence, not the source of truth.

---

## Cross-check package metadata

For packages with `metadata_object`, the checker must import the metadata object
and validate:

- `package_name` equals registry `package`;
- `import_name` equals registry `import_name`;
- profile-to-`ImplementationStatus` mapping is consistent:
  - `implemented` → `IMPLEMENTED`;
  - `partial_runtime` → `PARTIAL`;
  - `scaffolded` → `SCAFFOLDED`;
  - `orchestration_partial` → `PARTIAL`;
- validation-status expectations are consistent:
  - `implemented` must be `AVAILABLE`;
  - `scaffolded` must be `NOT_STARTED`;
  - `partial_runtime` and `orchestration_partial` must be `PENDING`.

If a package has no metadata object because it is shared, the registry must mark
`component_type = "shared"` and the checker must apply the shared profile only.

---

## Evidence requirements by profile

### `implemented`

Required for `frtb-ima` and `frtb-rrao`:

- package imports successfully;
- package `README.md`;
- package `CHANGELOG.md`;
- package `AGENTS.md`;
- package tests directory exists and contains public API tests;
- package or module regulatory traceability documentation exists;
- package or module regulatory assumptions documentation exists;
- module documentation root exists;
- module model documentation pack exists at
  `docs/modules/<module>/model_documentation/README.md`;
- requirement registry exists under `docs/modules/<module>/requirements/`;
- package source files exist under `src/<import_name>/`;
- package metadata reports implemented status;
- public calculation entry point imports successfully;
- each package declares a `public-api` `required_tests` entry whose path exists.

### `partial_runtime`

Required for `frtb-drc`:

- package imports successfully;
- package `README.md`;
- package `CHANGELOG.md`;
- package `AGENTS.md`;
- package tests directory exists;
- scaffold/public API tests exist;
- module documentation root exists;
- architecture/data design exists;
- detailed requirements exist;
- issue breakdown or decisions/plan exists;
- regulatory requirements or traceability documentation exists;
- requirement registry exists under `docs/modules/frtb-drc/requirements/`;
- package source files exist under `src/frtb_drc/`;
- package metadata reports partial status;
- public calculation entry point imports successfully;
- registry declares `public-api` and `unsupported-runtime-paths`
  `required_tests` entries whose paths exist.

Do not require a full IMA/RRAO-style model documentation pack for DRC in the
first PR unless substantive content is added. A placeholder pack is not
acceptable evidence.

### `scaffolded`

Required for `frtb-sbm` and `frtb-cva`:

- package imports successfully;
- package `README.md`;
- package `CHANGELOG.md`;
- package `AGENTS.md`;
- package scaffold test exists;
- module documentation root exists;
- regulatory requirements or PRD exists;
- requirement registry exists under `docs/modules/<module>/requirements/`;
- package metadata reports scaffolded status;
- public calculation entry point imports successfully;
- public calculation entry point raises
  `NotImplementedCapitalComponentError`;
- registry declares `scaffold-boundary` `required_tests` entry whose path
  exists.

### `orchestration_partial`

Required for `frtb-orchestration`:

- package imports successfully;
- package `README.md`;
- package `CHANGELOG.md`;
- package `AGENTS.md`;
- package tests directory exists;
- orchestration scaffold or standardised aggregation tests exist;
- module documentation root exists;
- package metadata reports partial status;
- public suite calculation entry point imports successfully;
- unsupported suite aggregation path fails explicitly until implemented;
- registry declares `orchestration-boundary` `required_tests` entry whose path
  exists.

No full model documentation pack is required for orchestration in the first PR.

### `shared`

Required for `frtb-common`:

- package imports successfully;
- package `README.md`;
- package `CHANGELOG.md`;
- package `AGENTS.md`;
- package tests directory exists;
- module documentation root exists;
- `py.typed` exists if the package declares typed distribution support;
- if shared regulatory helpers are present, registry declares
  `regulatory-helpers` `required_tests` entry whose path exists.

---

## DRC evidence pre-check

Before implementing the first PR, verify the `partial_runtime` requirements
against the current `frtb-drc` state by running the checker or manually
inspecting the file tree. The following items are expected to be present based
on the file tree at the time this spec was written:

| Requirement | Expected path | Status |
| --- | --- | --- |
| Module documentation root | `docs/modules/frtb-drc/` | Present |
| Architecture/data design | `docs/modules/frtb-drc/ARCHITECTURE_AND_DATA_DESIGN.md` | Present |
| Detailed requirements | `docs/modules/frtb-drc/DETAILED_REQUIREMENTS.md` | Present |
| Issue breakdown / decisions | `docs/modules/frtb-drc/ISSUE_BREAKDOWN.md` | Present |
| Regulatory requirements | `docs/modules/frtb-drc/REGULATORY_REQUIREMENTS.md` | Present |
| Requirement registry | `docs/modules/frtb-drc/requirements/BASEL_FRTB_DRC.yml` | Present |
| Package source files | `packages/frtb-drc/src/frtb_drc/` | Present |
| Package README | `packages/frtb-drc/README.md` | Present |
| Package CHANGELOG | `packages/frtb-drc/CHANGELOG.md` | Present |
| Package AGENTS | `packages/frtb-drc/AGENTS.md` | Present |
| Public API tests | `packages/frtb-drc/tests/test_drc_public_api.py` | Present |
| Public entry point importable | Verify `calculation_entrypoint` in registry | **Verify** |
| Unsupported paths fail explicitly | Registry `required_tests` entry with id `unsupported-runtime-paths` | **Verify** |

The implementer must run the checker against the actual current state before
adding any new evidence files. Do not add evidence files speculatively; only add
what the checker reports as missing.

---

## Make targets

Add these targets to the root `Makefile`:

```make
import-smoke:
	uv run python scripts/ci/import_smoke.py

maturity-check:
	mkdir -p dist/quality
	uv run python scripts/ci/check_package_maturity.py --json-output dist/quality/package-maturity.json

quality-control: import-smoke maturity-check
```

`quality-control` must be fast enough to run on every PR. It must not run the
full test suite, mutation tests, notebooks, benchmarks, or dependency audit.

---

## CI requirements

Add a `quality-control` job to `.github/workflows/ci.yml`.

The job must:

- run on every pull request to `main`;
- run on every push to `main`;
- **have no `needs: changes` dependency and no `if:` condition** — it runs
  unconditionally; this is what allows branch protection to require it without
  pending or skipped check statuses on docs-only, dependency-only, and
  workflow-only PRs;
- install uv and Python 3.11;
- run `uv sync --locked`;
- run `make quality-control`;
- upload `dist/quality/package-maturity.json` as an artifact when present.

The job name must be stable: `quality-control`.

The existing changed-path classifier can remain for expensive jobs. This job is
exempt from path-based skipping by design.

**`docs/REPO_CONTROLS.md` must be updated in the same PR** to add
`quality-control` to the required-checks table. Without this update, the job
runs but branch protection does not enforce it.

---

## Tests

Quality-control script tests must live under `tests/quality/`. The first PR must
update root `pyproject.toml` so pytest discovery includes both package tests and
root quality-control tests:

```toml
[tool.pytest.ini_options]
testpaths = ["packages", "tests"]
```

Add unit tests for:

- valid registry loading;
- duplicate package entries;
- duplicate import names;
- unknown maturity profile;
- missing package path;
- package directory omitted from registry;
- metadata mismatch between registry and `PACKAGE_METADATA`;
- missing or duplicate `required_tests` ids;
- missing `required_tests` paths;
- implemented profile requirements;
- partial-runtime profile requirements;
- scaffolded profile requirements and explicit not-implemented calculation
  behavior;
- orchestration-partial profile requirements;
- shared profile requirements;
- import-smoke success;
- import-smoke failure reporting.

Tests should use temporary fixture directories and synthetic modules where
possible. They must not depend on mutating the real package registry.

---

## Acceptance criteria

The first PR is complete when:

- `make import-smoke` passes on `origin/main`;
- `make maturity-check` passes on `origin/main`;
- `make quality-control` passes on `origin/main`;
- `make docs-check` passes;
- `make check` passes;
- root `pyproject.toml` pytest discovery includes `tests` so
  `tests/quality/` runs under `make check`;
- CI exposes a passing `quality-control` check for docs-only, code, dependency,
  and workflow PRs — confirm this by inspecting the PR check list before merge;
- `docs/REPO_CONTROLS.md` required-checks table includes `quality-control`;
- the registry accurately reflects package status and does not contradict
  package metadata;
- no scaffolded package is forced to provide implemented-package model evidence;
- no implemented package can silently lose required evidence files.

---

## Implementation sequence

1. Add IMA `PACKAGE_METADATA` and export it from `frtb_ima`.
2. Add the TOML registry with all current packages, including IMA
   `metadata_object = "frtb_ima:PACKAGE_METADATA"` and
   `calculation_entrypoint = "frtb_ima:models_based_capital_for_policy"`.
3. Add the registry loader and validation primitives.
4. Add the import smoke script and tests.
5. Add maturity profile checks and tests.
6. Update root pytest discovery so `tests/quality/` is included in `make check`.
7. Add Make targets.
8. Run `make maturity-check` against the current state and add only the minimum
   DRC evidence files reported missing; refer to the
   [DRC evidence pre-check](#drc-evidence-pre-check) table.
9. Wire the CI `quality-control` job with no `needs:` or `if:` guard.
10. Update `docs/REPO_CONTROLS.md` required-checks table.
11. Run the full local verification set from the acceptance criteria.
12. Open the PR with the registry, scripts, tests, CI job, and repo-controls
    update in one reviewable slice.

---

## Follow-on controls

Each phase below requires its own spec before implementation begins. Do not
implement any phase from the brief below; use it as a sequencing guide.

### Phase 2 — coverage and mutation enforcement

**Dependencies:** Phase 1 merged and trusted.

**Coverage floor for `implemented` packages.**
`docs/quality/coverage_policy.md` currently defines a 90% floor for
`frtb-ima` only. Extend the policy and `scripts/ci/check_module_coverage.py`
to enforce the same floor for every package whose maturity is `implemented`.
`frtb-rrao` is `implemented` and currently has no coverage floor. The Makefile
`test` target must collect coverage for all implemented packages, not only IMA.

**Mutation score floor enforcement.**
`mutation.yml` runs weekly but does not fail if the killed score drops below the
documented baseline (`75.12%` IMA, `85.47%` RRAO). Add
`scripts/ci/check_mutation_score.py` that reads mutmut results and fails below
the floor. Wire it into the weekly workflow so score rot is caught before a
release.

**Mutation baseline directory structure.**
Standardise to `docs/quality/<package>/mutation_baseline.md` and
`docs/quality/<package>/mutation_survivors.md` for every package. Move the
current IMA files from `docs/quality/` to `docs/quality/frtb-ima/` to match
the RRAO layout.

**Mutation artifact upload.**
`mutation.yml` currently uploads no artifacts. Add an
`actions/upload-artifact` step so results are inspectable without reading raw
logs.

### Phase 3 — profile promotion governance

**Dependencies:** Phase 1 merged.

Define the rules for flipping a package maturity in the registry:

- An ADR entry is required for any promotion (`scaffolded` → `partial_runtime`
  → `implemented`).
- The ADR must reference the evidence files that justify the promotion.
- A CODEOWNERS rule restricting `docs/quality/package_maturity.toml` to
  designated reviewers may be added when the registry feeds external or
  regulatory artefacts.

Until this phase lands, the interim rule applies: any PR that changes a
maturity status requires a human reviewer approval and a changelog entry.

### Phase 4 — regulatory quality scanner

**Dependencies:** Phase 1 merged.

Implement `scripts/ci/check_regulatory_quality.py` as a CI gate that fails for:

- banned language in source files and documentation (`prototype`, `toy`,
  `placeholder`, `TODO` inside regulatory thresholds);
- numerical constants in calculation modules without a regulatory citation in
  the same file;
- public API docstrings that are missing a Basel paragraph reference;
- source-manifest citations that reference documents not listed in
  `regulatory_sources.yml`.

Do not add this as a merge-blocking gate until the scanner has been run against
the full codebase and a suppression mechanism exists for intentional deviations.

### Phase 5 — diff-sensitive change classifier evidence gates

**Dependencies:** Phases 1 and 3 merged.

Extend the change classifier to require evidence updates when specific paths
change:

- formula or threshold change in `src/` → ADR required;
- public API change → changelog entry and test required;
- fixture update → version bump required;
- maturity status change → ADR and reviewer required (see Phase 3).

This gate must use the package maturity registry to determine which packages
are in scope for each rule.

### Phase 6 — AI advisory PR review

**Dependencies:** Phase 1 merged, at least one human reviewer approval required.

Add an advisory AI review summary as a GitHub Actions step or bot comment. It
must never block merges. It is informational only until the deterministic gates
from earlier phases are fully trusted and branch protection is confirmed to be
correctly wired.

### Phase 7 — supply-chain and compliance controls

**Dependencies:** Phase 1 merged.

These are bank-grade table stakes not currently in the control plane:

- Secrets scanning (GitHub secret scanning or equivalent) enabled on the
  repository.
- License compliance check added to `make audit-deps` or a separate Make target.
- SLSA provenance attestation verification added to the release workflow beyond
  the current `actions/attest-build-provenance` generation.
- CODEOWNERS expanded from `@tomanizer` catch-all to per-package owners as
  packages move to `implemented`.

Each of these requires a separate spec entry. Record the decision to defer them
here as intentional scope control, not a gap.
