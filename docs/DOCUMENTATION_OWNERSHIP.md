# Documentation ownership and canonical sources

This map defines which document is authoritative for each documentation domain
in `frtb-capital`. When two documents disagree, update the canonical source
first, then update summaries and historical plans to point back to it.

Outputs from this suite are synthetic engineering and validation evidence. They
are not final regulatory capital, regulatory submissions, legal opinions, or
supervisory approvals.

## Canonical ownership map

Use a two-tier package documentation layout:

- `docs/modules/<package>/` is the suite-facing module front door. It owns
  product requirements, regulatory requirements, architecture/design,
  public-API integration notes, issue plans, model documentation, and reviewer
  navigation for the package as a suite component.
- `packages/<package>/docs/` is the package-local evidence front door. It owns
  code-coupled regulatory traceability, regulatory assumptions, regulation
  summaries, source manifests, executable requirement registries, dataset
  contracts, validation packs, package journeys, and implementation evidence
  that should move with the package.

Do not duplicate canonical facts across both trees. Put the detailed source in
the owning tree and link to it from the other tree's README or navigation
pointer.

| Domain | Canonical source | Supporting sources | Owner of changes |
| --- | --- | --- | --- |
| Suite governance, worktree policy, release process, and repository controls | [AGENTS.md](../AGENTS.md), [AGENT_WORKTREE_POLICY.md](AGENT_WORKTREE_POLICY.md), [RELEASE_PROCESS.md](RELEASE_PROCESS.md), [REPO_CONTROLS.md](REPO_CONTROLS.md) | [CONTRIBUTING.md](../CONTRIBUTING.md), [.github workflows](../.github/workflows/) | Suite maintainers; material governance changes need an ADR or explicit governance note. |
| Architecture decisions and package-boundary rules | [ADR index](decisions/), especially [ADR 0002](decisions/0002-monorepo-structure.md), [ADR 0011](decisions/0011-core-runtime-dependency-policy.md), [ADR 0023](decisions/0023-arrow-tabular-handoff-boundary.md), and [ADR 0038](decisions/0038-suite-wide-attribution-impact-contract.md) | [ARCHITECTURE.md](ARCHITECTURE.md), [modules/README.md](modules/README.md) | ADR authors and affected package maintainers. |
| Regulatory corpus and source precedence | [regulatory/sources.yml](regulatory/sources.yml), [regulatory/CORPUS_POLICY.md](regulatory/CORPUS_POLICY.md), [regulatory/regimes/](regulatory/regimes/) | [regulatory/README.md](regulatory/README.md), package source manifests | Regulatory traceability maintainers; formula or profile changes require an ADR or material-change note. |
| Component regulatory crosswalks | [regulatory/crosswalk/](regulatory/crosswalk/) | Package-local traceability documents and requirement registries | Owning package maintainer plus regulatory traceability reviewer. |
| Package public API and runtime support status | [quality/package_maturity.toml](quality/package_maturity.toml), generated [quality/PACKAGE_STATUS.md](quality/PACKAGE_STATUS.md), package `README.md`, and `docs/modules/<package>/PUBLIC_API.md` where present | Package changelogs and suite [modules/README.md](modules/README.md) | Owning package maintainer; registry changes must keep generated status output current. |
| Package model documentation | `docs/modules/<package>/model_documentation/` where present, package `MODEL_DOCUMENTATION.md` where present | Package PRD, detailed requirements, architecture, and validation evidence | Owning package maintainer and model documentation reviewer. |
| Package-local traceability, source manifests, requirement registries, and validation packs | `packages/<package>/docs/REGULATION_SUMMARY.md`, `REGULATORY_TRACEABILITY.md`, `REGULATORY_ASSUMPTIONS.md`, `regulatory_sources.yml`, `requirements/`, and validation-pack docs where present | Suite [VALIDATION_PACK.md](VALIDATION_PACK.md), component crosswalks, `docs/modules/<package>/requirements/README.md` pointers | Owning package maintainer; cited runtime behavior must fail closed when mappings are incomplete. |
| Quality evidence and generated reports | [quality/](quality/), [quality/package_maturity.toml](quality/package_maturity.toml), [quality/CODE_DRIFT_CONTROLS.md](quality/CODE_DRIFT_CONTROLS.md), [performance/](performance/) | CI artifacts under `dist/` and package test evidence | Quality-control maintainers; generated reports must be regenerated through their scripts. |
| Result persistence and query evidence | [modules/frtb-result-store/STORAGE_CONTRACT.md](modules/frtb-result-store/STORAGE_CONTRACT.md), [modules/frtb-result-store/PUBLIC_API.md](modules/frtb-result-store/PUBLIC_API.md), [ADR 0034](decisions/0034-result-store-duckdb-parquet.md) | [modules/frtb-result-store/README.md](modules/frtb-result-store/README.md), package tests | Result-store maintainer; storage compatibility changes require schema-version evidence. |
| Suite orchestration and top-of-house aggregation | [modules/frtb-orchestration/README.md](modules/frtb-orchestration/README.md), [regulatory/crosswalk/frtb-orchestration.yml](regulatory/crosswalk/frtb-orchestration.yml), [ADR 0032](decisions/0032-orchestration-sa-arithmetic-and-fallback-routing.md) | [modules/standardised-approach.md](modules/standardised-approach.md), orchestration package tests | Orchestration maintainer; cross-component contract changes require an ADR. |

## Status vocabulary

Use these terms consistently in current evidence documents:

| Term | Meaning | Required evidence |
| --- | --- | --- |
| `implemented` | Deterministic public calculation path exists with cited requirements, package tests, public metadata, and maturity-registry evidence. | Top-level public API, required tests in `package_maturity.toml`, and linked regulatory crosswalk entries. |
| `partial_runtime` or `partial` | A cited runtime slice is supported, but other profiles, risk classes, methods, or evidence paths remain fail-closed. | Public API plus explicit unsupported-feature tests for incomplete paths. |
| `unsupported` | The feature or profile identity is recognised but must fail closed rather than approximate capital. | Runtime `UnsupportedRegulatoryFeatureError` or package-specific equivalent, plus negative tests or documented blocked evidence. |
| `comparison-only` | A jurisdiction or challenger reference is available for comparison, not as final capital authority. | Source status in the regulatory corpus and explicit non-final caution. |
| `placeholder` | A source, manifest, or historical issue-plan entry is intentionally incomplete and cannot drive capital by itself. | A linked follow-up, source-status note, or fail-closed runtime behavior. Current evidence docs must not use placeholder wording as a substitute for citations. |
| `not final regulatory capital` | Caution that prevents readers from treating synthetic examples or proposed-rule calculations as regulatory filings. | Keep the caution, but still cite the specific rule paragraph or unsupported-feature status for any calculation claim. |

Avoid generic `prototype` wording in current evidence documents. Prefer a
specific statement such as "synthetic engineering and validation evidence, not
final regulatory capital" and then cite the implemented or unsupported rule
path.

## Stale-roadmap handling

Historical planning documents, including `ISSUE_BREAKDOWN.md` files, may retain
delivered issue text when they are clearly labeled as historical. Current
status pages, PRDs, public API docs, validation-pack docs, and package-local
traceability documents must not say future docs or validation packs need to be
added when they already exist. Convert those statements into one of:

- a link to the canonical source;
- a dated historical note;
- an explicit follow-up issue; or
- an unsupported/fail-closed status with cited evidence.

The lightweight staleness check in `scripts/ci/check_docs_staleness.py` scans
current evidence documents for the riskiest wording while allowing this
ownership map, corpus policy, and historical audit docs to define vocabulary.
