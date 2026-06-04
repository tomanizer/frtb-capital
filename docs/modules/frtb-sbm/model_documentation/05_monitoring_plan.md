# Monitoring Plan

## CI Sentinels

Before pushing SBM package-code, documentation, or traceability changes, run:

- `make agent-guard`;
- affected SBM tests, especially `uv run pytest packages/frtb-sbm/tests`;
- `make quality-control`;
- `make changed-code-check` for substantial refactoring;
- `make drift-check` and `make test-value-check` when fixture values or hashes
  change.

## Drift Controls

Monitor these evidence points:

- fixture expected outputs and input hashes;
- profile/reference-data hashes;
- row, batch, and Arrow parity tests;
- unsupported-feature tests for profiles and sub-features;
- benchmark budget artifacts for batch and Arrow paths;
- regulatory crosswalk entries under `docs/regulatory/crosswalk/frtb-sbm.yml`.

## Review Triggers

Open a documentation update, ADR, or explicit traceability update when:

- any comparison profile becomes capital-producing;
- risk weights, correlations, or scenario-selection behavior changes;
- curvature branch logic or required evidence changes;
- audit/result fields change;
- analytical attribution or capital impact support boundaries change;
- fixture or benchmark baselines are replaced.
