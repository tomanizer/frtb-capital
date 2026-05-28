# Validation Engagement Charter

| Field | Value |
|-------|-------|
| Document owner | `<MODEL OWNER>` |
| Independent validator | `<MRM QUANT TEAM LEAD>` (Model Risk Management — quant) |
| Status | Draft for first agreement |
| Effective from | `<EFFECTIVE DATE>` |
| First scope | `frtb-ima` (other suite packages added by amendment) |
| Review cadence | Annual + on material change |
| Last updated | 2026-05-28 |

This charter is an internal working agreement between the development team and the independent Model Risk Management (MRM) quant team. It is not regulatory approval, supervisory authorisation, or a substitute for any external governance.

---

## 1. Purpose

To define how the FRTB capital suite is independently validated under SR 11-7 / PRA SS 1/23-style model risk controls, so that:

- Both teams agree on what is being validated, against what evidence, on what cadence.
- Findings have a tracked lifecycle from intake to closure.
- Material changes trigger re-validation through a documented workflow.
- The development team can build to the validator's evidence needs rather than guessing.

## 2. Scope

### In scope (initial)

| Item | Where it lives |
|------|---------------|
| `frtb-ima` calculation package | `packages/frtb-ima/` |
| FRTB-IMA model documentation pack | `docs/modules/frtb-ima/model_documentation/` |
| Architectural decisions | `docs/decisions/` (ADRs 0001 onward) |
| Requirement registry | `docs/modules/frtb-ima/requirements/` and `packages/frtb-ima/docs/requirements/NPR_2_0_MARKET_RISK.yml` |
| Audit records and replay CLI | `packages/frtb-ima/src/frtb_ima/audit.py`, `packages/frtb-ima/src/frtb_ima/replay.py` |
| Committed regression fixture | `packages/frtb-ima/tests/fixtures/capital_run_v1/` |
| Independent numerical reference vectors | `packages/frtb-ima/tests/test_reference_vectors.py` |
| Determinism guarantee | `packages/frtb-ima/tests/test_determinism.py` |

### Out of scope (this engagement)

- Sibling suite packages (`frtb-drc`, `frtb-cva`, `frtb-rrao`, `frtb-sa-sbm`). Each is added by a charter amendment when ready for validation.
- Upstream risk-engine outputs (market data, scenario generation, trade valuation). Validated separately by their respective owners.
- Firm-level capital consolidation, SA/IMA aggregation, and regulatory reporting submission.
- Supervisory approval. This charter governs internal validation only.

## 3. Parties and roles

| Role | Owner | Responsibility |
|------|-------|---------------|
| Model owner | `<NAME>` | Day-to-day stewardship of the model, response to findings, change management |
| Lead validator | `<MRM QUANT LEAD>` | Independent assessment, finding triage, sign-off recommendation |
| Validation reviewers | `<MRM QUANT REVIEWERS>` | Numerical and conceptual review |
| Head of model risk | `<NAME>` | Approves sign-off recommendations, escalation point |
| Model governance forum | `<NAME OF COMMITTEE>` | Oversight of materially-changed models and use restrictions |
| Engineering lead | `<NAME>` | Codebase steward, finding-remediation delivery |

Independence requirement: validation reviewers must not have written or owned the code paths under review. Engineering and MRM operate in separate review chains; reviewers on a finding-remediation PR cannot also be reviewers on the validation finding that prompted it.

## 4. Engagement artifacts

The development team commits to maintaining the following artifacts as the evidence basis for validation. MRM accesses them at a tagged release.

| Artifact | Purpose for validation |
|----------|------------------------|
| Model documentation pack (`docs/modules/frtb-ima/model_documentation/`) | Conceptual soundness, intended use, derivation, assumptions and limitations, sensitivity analysis, monitoring, change history |
| Architectural decision records (`docs/decisions/`) | Why specific methodology choices were made |
| Requirement registry (`NPR_2_0_MARKET_RISK.yml`) | Boundary of claimed implementation — every requirement labelled `implemented`, `partial`, `out_of_scope`, or `unsupported` |
| Regulatory traceability (`packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md`) | Code-to-regulation and regulation-to-code mapping |
| Material change policy (ADR #5 `docs/decisions/0005-material-change-policy.md`) | Definition of material change and re-validation trigger |
| Audit records (`DeskAuditRecord`, `CapitalRunAuditLog`) | Per-run identity: `model_version`, `code_version`, `policy_hash`, `inputs_hash`, full result breakdown |
| Replay CLI (`packages/frtb-ima/src/frtb_ima/replay.py`) | Independent reproduction of any committed audit record from inputs |
| Committed fixture (`tests/fixtures/capital_run_v1/`) | Reference inputs and expected outputs for regression and replay |
| Reference-vector tests (`test_reference_vectors.py`) | Closed-form analytic checks for ES, KS, Spearman, multiplier |
| Determinism registry (`tests/fixtures/determinism/<py-minor>.sha256`) | Cross-Python-minor reproducibility guarantee |
| Mutation testing baseline (`docs/quality/mutation_baseline.md`) | Test-suite robustness evidence |
| Coverage policy (`docs/quality/coverage_policy.md`) | 90% interim, 95% production-quality target per module |

## 5. Validation deliverables

### 5.1 Initial validation report

A single document covering, at minimum:

- **Conceptual soundness:** are the implemented formulas and aggregation rules consistent with Basel MAR31-MAR33 and U.S. NPR 2.0 as cited?
- **Numerical accuracy:** do outputs match independent reference calculations within stated tolerance? Are determinism claims verifiable?
- **Implementation review:** are the cited regulatory parameters correctly placed in policy and consistently applied?
- **Outcome analysis:** what do trailing backtesting and PLA results say about model fit on representative portfolios?
- **Limitations and use restrictions:** what is the model approved for, and what is it not?
- **Findings register:** open findings, severity, recommended remediation.

Expected duration: 3–6 months from kickoff to first report.

### 5.2 Findings register

Continuously maintained throughout the engagement. Each finding is filed as a GitHub issue with the `validation-finding` label and the following minimum fields:

- Severity (high / medium / low — see §7)
- Affected calculation module(s) and requirement IDs
- Reference evidence (script, fixture, calculation, citation)
- Remediation owner
- Status (open / in-remediation / closed / accepted-with-restriction)

### 5.3 Periodic re-validation

- Annual re-validation review against the most recent tagged release.
- Material-change re-validation triggered by the rules in ADR #5.
- Ongoing-monitoring review against backtesting and PLA outputs (cadence TBD with MRM — typically quarterly).

### 5.4 Sign-off recommendation

At the conclusion of the initial validation pass, the lead validator issues one of:

- **Approved for stated use** — no open high-severity findings.
- **Approved with restrictions** — specified scope or compensating controls required.
- **Not approved** — material findings preclude use; remediation plan agreed.

The head of model risk approves the recommendation. The model governance forum is informed.

## 6. Cadence and milestones

| Milestone | Owner | Target |
|-----------|-------|--------|
| Charter signed | Both teams | `<DATE>` |
| Engagement kickoff | Lead validator + model owner | Charter + 2 weeks |
| Documentation review complete | Lead validator | Kickoff + 4 weeks |
| Conceptual review complete | Lead validator | Kickoff + 8 weeks |
| Numerical / empirical review complete | Lead validator | Kickoff + 12 weeks |
| Draft findings circulated | Lead validator | Kickoff + 14 weeks |
| Remediation cycle (per high finding) | Model owner | Per finding SLA in §7 |
| Sign-off recommendation | Lead validator | Kickoff + 20 weeks (subject to remediation) |
| Head of model risk approval | Head of model risk | Recommendation + 2 weeks |

These are planning targets, not contractual deadlines.

## 7. Findings lifecycle

### Severity classification

| Severity | Definition | Engineering triage SLA | Default remediation SLA |
|----------|------------|------------------------|-------------------------|
| High | Materially affects capital output, misinterprets a regulatory requirement, or invalidates the reproducibility claim | 2 business days | 4 weeks |
| Medium | Affects calculation in edge cases, ambiguous documentation, missing test coverage on a regulatory-critical path | 5 business days | 8 weeks |
| Low | Cosmetic, documentation polish, non-regulatory test gap | 10 business days | Next minor release |

### Intake and tracking

- Filed as GitHub issues with the `validation-finding` label in `tomanizer/frtb-capital`.
- Severity is set by the lead validator at intake. Engineering may dispute via comment; resolution by head of model risk.
- A finding is closed only when (a) the validator agrees the remediation evidence is sufficient, or (b) the head of model risk accepts the finding under documented compensating controls or use restrictions.

### Use restrictions while open

A model with open high-severity findings is in **validated-with-restrictions** state. The restrictions are recorded in the model documentation pack and the audit record metadata until the findings are closed or accepted.

## 8. Change management

### Material changes

Material changes are defined in ADR #5 (`docs/decisions/0005-material-change-policy.md`). When a material change merges:

- The audit record `model_version` increments per the ADR-defined semver rule.
- The validation engagement re-opens for the affected scope.
- The finding register is updated with any open items rolled forward.
- A re-validation report (lighter weight than initial) is produced before the change is considered validated.

### Non-material changes

Non-material changes do not trigger re-validation but are listed in the model documentation pack's change history.

### Model lifecycle states

| State | Meaning | Audit-record metadata |
|-------|---------|----------------------|
| `in_development` | Not yet entered validation | `validation_status: "in_development"` |
| `under_validation` | Initial validation in progress | `validation_status: "under_validation"` |
| `validated` | Validated for stated use; no open high findings | `validation_status: "validated"` |
| `validated_with_restrictions` | Validated with documented restrictions or compensating controls | `validation_status: "validated_with_restrictions"` |
| `suspended` | Use suspended pending remediation | `validation_status: "suspended"` |
| `retired` | No longer in use | `validation_status: "retired"` |

This metadata is *not yet* on audit records — adding it is a tracked engineering item triggered by this charter coming into effect.

## 9. Governance and escalation

- Routine disagreements between model owner and lead validator: resolved by direct discussion, recorded in the finding comment trail.
- Material disagreement on severity, scope, or sign-off: escalated to the head of model risk.
- Material disagreement involving the head of model risk: escalated to the model governance forum.
- Disagreement on regulatory interpretation: external counsel consulted before sign-off.

## 10. Documentation maintenance

- This charter is reviewed annually and on each material expansion of scope (e.g., adding `frtb-drc` to in-scope).
- Amendments are made by PR, reviewed by both the model owner and lead validator, and merged through the standard protected-branch workflow.
- Prior versions are retrievable through git history; the current version always reflects the active agreement.

## 11. References

- Federal Reserve / OCC SR 11-7 — *Guidance on Model Risk Management*
- PRA SS 1/23 — *Model risk management principles for banks*
- Basel Committee on Banking Supervision — *Minimum capital requirements for market risk* (MAR30–MAR33)
- U.S. NPR 2.0 (March 2026 proposed rule) — proposed §§ `__.212`–`__.215`
- EU CRR Articles 325ba–325bk; Delegated Regulations (EU) 2022/2059 and 2022/2060
- Internal: `docs/decisions/` (ADRs)
- Internal: `packages/frtb-ima/docs/REGULATORY_TRACEABILITY.md`
- Internal: `docs/RELEASE_PROCESS.md`
- Internal: `packages/frtb-ima/docs/regulatory_sources.yml`

## 12. Acknowledgement

Signed acknowledgement of this charter establishes the working agreement between teams. It does not constitute regulatory approval, supervisory authorisation, or model validation in itself; those are the outcomes the engagement is set up to produce.

| Role | Name | Date |
|------|------|------|
| Model owner | `<NAME>` | `<DATE>` |
| Lead validator | `<NAME>` | `<DATE>` |
| Head of model risk | `<NAME>` | `<DATE>` |
