# Monitoring Plan

## CI Sentinels

Before pushing CVA package-code, documentation, or traceability changes, run:

- `make agent-guard`;
- affected CVA tests, especially `uv run pytest packages/frtb-cva/tests`;
- `make quality-control`;
- `make changed-code-check` for substantial refactoring;
- `make drift-check` and `make test-value-check` when fixture values or hashes
  change.

`make package-status-dashboard` must stay clean whenever
`docs/quality/package_maturity.toml`, package metadata, or required-test
evidence changes.

## Drift Controls

Monitor these evidence points:

- BA-CVA and SA-CVA fixture expected outputs;
- profile hashes and reference-data hashes;
- public API and unsupported-feature tests;
- row, batch, and Arrow batch parity;
- property tests for hedge benefit and aggregation behavior;
- audit serialization, replay, input hashes, and reconciliation invariants;
- regulatory crosswalk entries under `docs/regulatory/crosswalk/frtb-cva.yml`.

## Review Triggers

Open a documentation update, ADR, explicit traceability update, and focused
revalidation plan when:

- a new CVA profile becomes capital-producing;
- MAR50.9 or another unsupported method is implemented;
- a non-Basel comparison profile diverges numerically from the shared
  Basel-aligned mechanics;
- risk-weight, correlation, hedge, or qualified-index behavior changes;
- result fields or audit metadata change;
- fixture, comparator, profile-hash, source-manifest, or crosswalk baselines are
  replaced;
- production monitoring evidence is introduced as a package-owned validation
  artifact.

Changes to bank source-data controls, legal interpretation, supervisory
approval, and production monitoring remain outside `frtb-cva` unless a future
ADR moves those responsibilities into the package.
