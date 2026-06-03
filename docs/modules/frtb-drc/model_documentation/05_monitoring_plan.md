# Monitoring Plan

## CI Sentinels

Run the following before pushing package-code or model-documentation changes:

- `make agent-guard`;
- affected DRC tests, especially `uv run pytest packages/frtb-drc/tests`;
- `make quality-control`;
- `make changed-code-check` for substantial refactoring;
- `make drift-check` and `make test-value-check` when generated outputs,
  fixture hashes, or expected values change.

## Drift Controls

The fixture packs and public API tests are the main drift sentinels:

- fixture output hashes and result JSON must remain deterministic under row
  reordering;
- profile hashes must change when cited reference data changes;
- handoff schema tests must detect accidental Arrow-column contract drift;
- attribution reconciliation must remain exact or explicitly residual.

## Operational Review Triggers

Open a model-documentation or ADR update when any of these changes occur:

- risk-weight, bucket, HBR, or category aggregation formulas change;
- a previously unsupported profile or risk class becomes capital-producing;
- a result shape changes in a way that affects audit or orchestration handoff;
- fixture baselines grow or a fixture case is replaced;
- regulatory citations move from proposed comparison material to a final rule
  mapping.
