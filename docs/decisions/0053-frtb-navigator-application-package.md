# 53. FRTB Navigator application package boundary

Date: 2026-07-02

## Status

Proposed

## Context

The FRTB Navigator started under `tools/frtb_dashboard` as fixture-backed
FastAPI and React/Vite tooling. Issue #1141 promotes it to a first-class
workspace package so the application is visible to package metadata, maturity,
import-smoke, documentation, and quality-control checks.

The Navigator is not a capital calculation component. Its role is read-only
inspection of already-resolved result-store and orchestration read models.
Without an explicit boundary, application code could drift into capital
classification, result synthesis, or browser-side regulatory logic.

## Decision

`frtb-navigator` is a first-class workspace package with Python distribution
name `frtb-navigator`, import package `frtb_navigator`, product name
`FRTB Navigator`, and module docs under `docs/modules/frtb-navigator/`.

It is an application/read-model package:

- it may render, filter, cache, and inspect already-resolved API/read-model
  payloads;
- it may consume `frtb-result-store` read APIs and `frtb-orchestration` public
  read models;
- it may use component demo fixtures only when the fixture dependency is
  documented and covered by package-local tests;
- it must not calculate capital, classify regulatory inputs in the browser,
  generate shocks, interpolate surfaces, fetch raw object-store payloads
  directly, synthesize missing rows, or silently substitute zero for missing
  scoped rows.

Quality-control treats application packages separately from capital kernels via
the `application_partial` maturity profile. Import-linter enforces that capital,
orchestration, and storage packages do not import `frtb_navigator`.

## Consequences

The previous `tools/frtb_dashboard` path is retained only as a compatibility
shim. Active development, tests, docs, and frontend commands live under
`packages/frtb-navigator`.

Large fixture-backed modules moved from `tools/` into `packages/` are now visible
to drift and docstring controls. Follow-up simplification work is tracked by the
dedicated package health audit issue #1159, but the initial promotion preserves
behavior so the migration can be reviewed separately from refactoring.
