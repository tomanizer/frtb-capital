# Monitoring Plan

This monitoring plan covers the `frtb-ima` package as a calculation component.
It does not replace enterprise model-risk monitoring, desk governance, market
data controls, or supervisory reporting.

## Routine Monitoring

| Control | Frequency | Owner | Evidence |
| --- | --- | --- | --- |
| CI calculation gate (`make check`) | Every pull request and protected-branch merge | Engineering | GitHub checks for lint, typecheck, tests, examples, notebooks, dependency audit, and SBOM. |
| Coverage floor | Every test run | Engineering | Coverage JSON and per-module calculation-module coverage report. |
| Reference-vector tests | Every test run | Engineering / methodology | `packages/frtb-ima/tests/test_reference_vectors.py`. |
| Validation notebook execution | Every pull request | Engineering / validation reviewer | Notebook CI artifact and validation-pack manifest. |
| Dependency audit | Every pull request and weekly monitoring | Engineering / security | `make audit-deps` output and GitHub dependency-audit job. |
| SBOM generation | Every pull request | Engineering / security | CycloneDX artifact under `dist/sbom/`. |
| Requirement inventory review | At release and material model change | Package owner / methodology | `NPR_2_0_MARKET_RISK.yml` status diffs. |
| Assumptions and limitations review | At release and material model change | Package owner / model validation | `REGULATORY_ASSUMPTIONS.md` and this pack. |
| ADR review | For material model changes | Engineering, package owner, model validation, security when applicable | `docs/decisions/` entries and PR approvals. |

## Run-Level Monitoring

For each controlled capital run, retain:

- code version, package version, model version, policy hash, and input hashes;
- desk eligibility status;
- scenario, RFET, NMRF, PLA, and backtesting input lineage;
- desk-level `DeskAuditRecord` and run-level `CapitalRunAuditLog`;
- deterministic audit report and validation-pack manifest when notebooks are
  executed.

The runtime logging path is for operational visibility only. It must not become
the source of record for detailed regulatory audit evidence.

## Breach Response

| Breach | Immediate response | Follow-up |
| --- | --- | --- |
| CI failure on calculation or notebook gate | Block merge. Inspect failing job and reproduce locally where possible. | Fix in the same PR or split into a targeted follow-up if unrelated. |
| Coverage floor breach | Block merge unless the package owner approves a documented exception. | Add focused tests or revise the coverage policy with explicit rationale. |
| Reference-vector failure | Treat as potential model defect. Block merge. | Determine whether the code or reference vector changed and document the decision. |
| Requirement status drift | Block release until requirement inventory and traceability are reconciled. | Update requirement YAML, traceability docs, and assumptions. |
| Unexpected capital movement in fixture | Block merge if caused by unintended logic drift. | If intended, update fixture hashes and change history in the same PR with reviewer approval. |
| New regulatory interpretation | Open ADR-backed material-change work item before changing calculation outputs. | Update model documentation, traceability, tests, and release notes. |
| Dependency vulnerability | Follow `SECURITY.md` and block release for high-impact issues affecting runtime or CI integrity. | Patch, audit, and document SBOM/dependency changes. |

## Escalation

Escalate to model validation when:

- a material formula, parameter, estimator, or routing decision changes;
- a sensitivity or reference-vector test challenges a modelling choice;
- requirement status changes between `implemented`, `partial`, `unsupported`,
  and `out_of_scope`;
- a production-readiness claim is requested.

Escalate to security when:

- a runtime or development dependency vulnerability affects reproducibility or
  CI integrity;
- signing, SBOM, provenance, or release-attestation controls change.

Escalate to the package owner when:

- a PR crosses package boundaries;
- a change requires a version bump or ADR;
- a release note would change model-risk interpretation.
