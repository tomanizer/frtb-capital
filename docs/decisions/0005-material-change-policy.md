# 5. Material change policy and ADR-driven change control

Date: 2026-05-28

## Status

Accepted

## Context

`frtb-capital` contains market-risk capital models that are expected to be
reviewed against SR 11-7 / PRA SS 1/23-style model-risk controls. A change that
can alter model outputs, regulatory interpretation, model boundaries, or audit
evidence needs stronger review than a refactor or documentation update.

The repository needs one canonical definition of a material model change so
contributors, reviewers, and automated agents can decide when an ADR, model
owner approval, validation review, version bump, changelog entry, and fixture
review are required.

## Decision

A **material change** is any change that does at least one of the following:

- changes a regulatory threshold, multiplier, confidence level, correlation
  parameter, traffic-light boundary, observation-count rule, or policy default;
- changes a calculation formula, estimator, aggregation method, input routing
  rule, sign convention, or required input set;
- changes `RegulatoryPolicy`, `ModelVersion`, or public package API field
  types, names, defaults, or semantics;
- changes the numerical values in a committed golden fixture such as
  `expected_outputs.json` beyond pure rounding or display formatting;
- changes requirement status between `implemented`, `partial`, `unsupported`,
  and `out_of_scope`;
- changes package boundaries, supported regimes, model identifiers, audit-record
  semantics, policy hashes, input hashes, or reproducibility claims;
- changes release/versioning semantics for a model package.

Material changes require:

1. an ADR under `docs/decisions/`;
2. package-owner approval for every affected package;
3. model-validation reviewer approval before merge;
4. a package version bump when a package model changes;
5. root and package changelog entries as applicable;
6. fixture regeneration and review when fixture outputs or hashes change;
7. updated traceability, requirement inventory, model documentation, and tests
   when the change affects those artifacts.

The PR must explain why the change is material, link the ADR, and identify the
expected validation evidence.

## Non-Material Changes

The following are non-material when they preserve public semantics and
calculation outputs:

- code refactoring with identical golden output and unchanged public API;
- documentation-only changes that do not reinterpret regulatory treatment;
- test additions or test rewrites that do not alter production code or fixtures;
- performance optimisations with identical outputs and unchanged audit records;
- formatting, lint, typo, CI ergonomics, and dependency-audit workflow changes
  that do not affect runtime package behaviour.

Non-material changes still need normal review, local verification, and
changelog entries when user-facing documentation or release notes should record
the change.

## Workflow

1. Classify the change before implementation.
2. If material, draft or update the ADR before changing code.
3. Implement the change with tests, traceability, model-documentation, and
   fixture updates in the same PR unless the ADR explicitly stages the rollout.
4. Run the repository verification gate.
5. Resolve all review conversations before merge.
6. Merge through the protected-branch PR workflow.
7. Include the ADR and material-change summary in the next release notes.

If reviewers disagree about whether a change is material, treat it as material
until the model owner and model-validation reviewer document a non-material
decision in the PR.

## Backfilled Decisions

The following prior decisions are material model-design evidence and are
recorded as ADRs:

- [ADR 0003](0003-sa-drc-cva-scope.md): SA component stack and CVA as separate packages
  within the suite.
- [ADR 0004](0004-weighted-interpolated-expected-shortfall.md): weighted
  interpolated expected shortfall estimator.
- [ADR 0006](0006-type-a-nmrf-zero-correlation-ses.md): Type A NMRF
  zero-correlation SES aggregation.
- [ADR 0007](0007-pla-metric-policy-by-regime.md): Fed KS-only PLA versus
  EU/PRA KS + Spearman PLA.
- [ADR 0008](0008-nested-liquidity-horizon-vectors.md): nested
  liquidity-horizon vectors rather than scalar scaling.
- [ADR 0009](0009-desk-eligibility-two-state-guard.md): desk eligibility as a
  two-state capital guard.

## Consequences

**Positive:**

- Review expectations are explicit.
- Model validation sees material methodology changes before merge.
- Release notes and model documentation have a stable decision trail.

**Negative:**

- Some changes require more up-front documentation.
- Agents must check whether a formula, fixture, policy, or model-boundary change
  needs an ADR before editing.

## References

- [CONTRIBUTING.md](../../CONTRIBUTING.md).
- [docs/RELEASE_PROCESS.md](../RELEASE_PROCESS.md).
- [docs/modules/frtb-ima/model_documentation/06_change_history.md](../modules/frtb-ima/model_documentation/06_change_history.md).
- `tomanizer/frtb-capital` issue #16.
