# Monitoring Plan

## CI Sentinels

Before pushing CVA package-code, documentation, or traceability changes, run:

- `make agent-guard`;
- affected CVA tests, especially `uv run pytest packages/frtb-cva/tests`;
- `make quality-control`;
- `make changed-code-check` for substantial refactoring;
- `make drift-check` and `make test-value-check` when fixture values or hashes
  change.

## Drift Controls

Monitor these evidence points:

- BA-CVA and SA-CVA fixture expected outputs;
- profile hashes and reference-data hashes;
- public API and unsupported-feature tests;
- row, batch, and Arrow handoff parity;
- property tests for hedge benefit and aggregation behavior;
- regulatory crosswalk entries under `docs/regulatory/crosswalk/frtb-cva.yml`.

## Review Triggers

Open a documentation update, ADR, or explicit traceability update when:

- a new CVA profile becomes capital-producing;
- MAR50.9 or another unsupported method is implemented;
- risk-weight, correlation, hedge, or qualified-index behavior changes;
- result fields or audit metadata change;
- fixture or comparator baselines are replaced.
