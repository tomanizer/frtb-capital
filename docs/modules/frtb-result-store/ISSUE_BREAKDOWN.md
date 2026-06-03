# frtb-result-store issue breakdown

This document breaks [DETAILED_DESIGN.md](DETAILED_DESIGN.md) into
GitHub-sized implementation issues. Each issue should stay scoped to
`frtb-result-store` unless explicitly noted.

GitHub parent tracker: [#457](https://github.com/tomanizer/frtb-capital/issues/457).

## GitHub Issue Map

| Issue | Title |
| --- | --- |
| [#445](https://github.com/tomanizer/frtb-capital/issues/445) | Canonical run identity, run groups, and status events |
| [#446](https://github.com/tomanizer/frtb-capital/issues/446) | Configurable hierarchy management and canonical capital graph generation |
| [#447](https://github.com/tomanizer/frtb-capital/issues/447) | Strict artifact schema registry and chunked writer |
| [#448](https://github.com/tomanizer/frtb-capital/issues/448) | Required artifact validation and single-run commit staging |
| [#449](https://github.com/tomanizer/frtb-capital/issues/449) | Schema compatibility, input manifests, events, and OpenTelemetry |
| [#450](https://github.com/tomanizer/frtb-capital/issues/450) | Persisted Parquet marts |
| [#451](https://github.com/tomanizer/frtb-capital/issues/451) | Movement and attribution storage expansion |
| [#452](https://github.com/tomanizer/frtb-capital/issues/452) | S3 Parquet backend mode |
| [#453](https://github.com/tomanizer/frtb-capital/issues/453) | Read-only FastAPI service |
| [#454](https://github.com/tomanizer/frtb-capital/issues/454) | Artifact drillthrough API |
| [#455](https://github.com/tomanizer/frtb-capital/issues/455) | Read-only SQL helper, admin CLI, and one-way export |
| [#456](https://github.com/tomanizer/frtb-capital/issues/456) | Full reporting mart expansion and performance checks |

## Issue 1 — Canonical run identity, run groups, and status events

Depends on: initial `frtb-result-store` package.

Scope:

- deterministic `run_id` generation;
- deterministic `run_group_id` generation;
- `RunStatus` enum;
- append-only `RunStatusEvent`;
- latest-status query helper;
- manifest fields for run identity payloads;
- full-digest storage IDs generated with `frtb_common.hashing.stable_json_hash`;
- prefix alias collision detection when prefix lookup is supported;
- explicit existing-`run_id` recommit policy;
- import-linter forbidden contracts for result-store package boundaries;
- kernel import-boundary exemption for `packages/frtb-result-store/src`;
- core import path that does not require DuckDB or OpenTelemetry.

Definition of done:

- same run identity payload produces the same `run_id`;
- different regime or input snapshot produces a different `run_id`;
- `run_id` uses the full digest, with short prefixes treated only as display or
  lookup aliases;
- ambiguous prefix lookups fail closed;
- re-committing an existing manifested `run_id` is rejected;
- run groups link comparable regime runs without merging child run identity;
- first committed run status is `CANDIDATE`;
- status changes are append-only events;
- result-store imports only `frtb-common` and approved third-party IO/query
  dependencies;
- capital packages, orchestration, and common do not import result-store;
- quality-control enforces the boundary and permits result-store PyArrow IO;
- package-local tests cover deterministic IDs and status history.

## Issue 2 — Configurable hierarchy management and canonical capital graph generation

Depends on: Issue 1.

Scope:

- default hierarchy dimensions: firm, legal entity, business line, desk,
  portfolio, book;
- `book_id` as the default lowest collection of trades or positions;
- hierarchy definition and hierarchy node storage;
- support for client-defined hierarchy levels and aggregation nodes;
- canonical hierarchy node ID generator;
- canonical FRTB capital node ID generator;
- per-node-family identity payload registry;
- canonical Unicode/date/datetime normalization rules;
- standard FRTB capital edge generator under the resolved hierarchy leaf;
- rejection of caller-supplied custom FRTB capital edges;
- graph validation for missing hierarchy dimensions.

Definition of done:

- equivalent hierarchy paths generate stable hierarchy node IDs across runs;
- equivalent FRTB dimensions generate stable capital node IDs under the same
  hierarchy leaf;
- node IDs use structured identity payloads and
  `frtb_common.hashing.stable_json_hash`, not raw colon-concatenated strings;
- every supported node family documents which fields participate in ID
  generation;
- standard business hierarchy edges are generated from the active
  `HierarchyDefinition`;
- standard FRTB capital graph edges are generated under the resolved hierarchy
  leaf;
- custom hierarchy levels are accepted without changing FRTB capital graph
  semantics;
- custom FRTB capital edges are not accepted in first pass;
- tests cover default firm-to-book hierarchy, a client-defined hierarchy, and
  component/risk-class/bucket drilldown.

## Issue 3 — Strict artifact schema registry and chunked artifact writer

Depends on: Issue 1.

Scope:

- artifact schema registry;
- controlled vocabulary registry for measure names and attribution target
  types;
- strict Arrow schemas and fingerprints;
- `ArtifactWriteRequest`;
- chunked/streaming artifact writer;
- ZSTD Parquet compression;
- artifact row/byte counts and partition metadata.

Definition of done:

- IMA P&L vector schema is implemented and tested;
- first-pass measure names and attribution target types are validated against
  registries;
- each chunk is validated before write;
- schema mismatch fails before commit;
- artifact refs record schema fingerprint and compression metadata;
- writer does not require full artifacts in memory.

## Issue 4 — Required-artifact validation and single-run commit staging

Depends on: Issues 2 and 3.

Scope:

- required artifact rules by component/result type;
- explicit conditional artifact expectation rows;
- staging area for base tables, artifacts, marts, and manifest;
- commit order that avoids partial committed runs;
- manifest-as-commit-marker protocol for local and future S3 layouts;
- cleanup on failed writes and abandoned staging objects.

Definition of done:

- IMA/SBM/DRC/RRAO/CVA component presence implies required artifact checks;
- conditional IMA tail and SBM correlation evidence is validated from declared
  expectations, not inferred circularly from artifact presence;
- missing required artifacts reject the run commit;
- failed commits leave no committed run manifest;
- readers ignore objects that are not referenced by a committed manifest;
- tests cover missing artifact, invalid artifact, and successful commit paths.

## Issue 5 — Schema compatibility, input snapshot manifests, events, and OpenTelemetry

Depends on: Issue 1.

Scope:

- run manifest schema-version and table/artifact/mart fingerprints;
- compatibility check on read/write;
- compact input snapshot manifest rows;
- result event stream;
- suggested status from events;
- compact run telemetry rows;
- OpenTelemetry trace/metric instrumentation through the lightweight API;
- standard logging correlation with trace context where available;
- trace context linkage from persisted telemetry rows where available.

Definition of done:

- incompatible schema version fails closed per run without making other
  compatible runs unreadable;
- input snapshot manifests are persisted and queryable;
- result events are separate from status events;
- error-level events suggest `REJECTED`;
- telemetry captures base-table write, artifact write, mart generation, catalog
  refresh, and export phases;
- OpenTelemetry spans use low-cardinality FRTB attributes such as `run_id`,
  `regime_id`, `as_of_date`, `component`, `artifact_type`, and `mart_name`;
- OpenTelemetry absence degrades to no-op instrumentation;
- importing core `frtb_result_store` contracts does not require OpenTelemetry;
- the package does not configure SDK/exporter/collector backends itself.

## Issue 6 — Persisted Parquet marts

Depends on: Issues 2 and 4.

Scope:

- persisted `capital_summary`;
- persisted `capital_tree`;
- persisted `component_breakdown`;
- extendable mart-generation framework;
- mart schema fingerprints.

Definition of done:

- marts are written as Parquet during run commit;
- dashboard query helpers read marts by default;
- mart schemas are versioned/fingerprinted;
- tests cover capital summary, tree ordering, and component totals.

Follow-on mart expansion:

- `top_contributors`;
- `movement_summary`;
- `regime_comparison`;
- `ima_desk_dashboard`;
- `sbm_bucket_ladder`;
- `drc_issuer_contributors`;
- `cva_counterparty_contributors`;
- `rrao_exposure_summary`.

## Issue 7 — Movement and attribution storage expansion

Depends on: Issues 2 and 6.

Scope:

- multi-target attribution rows;
- movement result rows;
- official movement storage;
- movement summary mart;
- attribution artifact references.

Definition of done:

- attribution target types include position, sensitivity, risk factor, issuer,
  counterparty, desk, portfolio, book, residual branch, and unsupported branch;
- attribution rows preserve `category`, `bucket_key`, and `marginal_multiplier`
  from `frtb_common.CapitalContribution`;
- movement rows link `run_id` and `baseline_run_id`;
- movement rows carry `base_currency`;
- movement summary is queryable by node;
- tests cover day-over-day and regime-over-regime movement fixtures.

## Issue 8 — S3 Parquet backend mode

Depends on: Issues 3 and 4.

Scope:

- `s3://` root support;
- DuckDB `httpfs` configuration hooks;
- URI-safe staging and commit behavior;
- S3 artifact and mart paths using the same logical layout as local mode.

Definition of done:

- local and S3 roots share the same logical table/artifact layout;
- S3 mode uses the same manifest-as-commit-marker reader contract as local mode;
- S3 mode can read and write Parquet artifacts and base tables in integration
  tests or a documented local mock;
- configuration avoids hard-coded credentials;
- DuckLake remains reserved.

## Issue 9 — Read-only FastAPI service

Depends on: Issues 1, 2, 6.

Scope:

- optional `api` dependencies;
- read-only FastAPI app factory;
- FRTB-specific endpoints for runs, run groups, capital tree, nodes, measures,
  artifacts, attribution, lineage, events, movements, and regime comparison;
- OpenAPI tags by FRTB domain;
- no write endpoints.

Definition of done:

- importing `frtb_result_store` does not require FastAPI;
- API serves run and capital-tree fixtures from a local store;
- API opens independent read-only or in-memory DuckDB connections over
  committed manifests and Parquet instead of sharing a mutable writer catalog;
- endpoints return documented schemas;
- no raw table-dump endpoint exists;
- tests use FastAPI test client.

## Issue 10 — Artifact drillthrough API

Depends on: Issues 3 and 9.

Scope:

- paged JSON artifact rows;
- column selection and simple filters;
- downloadable Parquet path/stream response;
- local-mode file serving;
- S3-mode URI handoff placeholder.

Definition of done:

- artifact page endpoint does not load the full artifact into memory;
- downloadable Parquet endpoint works in local mode;
- pagination is deterministic;
- invalid artifact id returns a clear 404-style response.

## Issue 11 — Read-only SQL helper, admin CLI, and one-way export

Depends on: Issues 1, 4, 6.

Scope:

- best-effort read-only DuckDB connection helper;
- CLI commands: inspect, list-runs, refresh-catalog, export-run, validate-store;
- single-run export with checksums;
- no import support;
- no lifecycle workflow management.

Definition of done:

- read-only connection prevents writes where DuckDB supports read-only mode;
- `catalog.duckdb` is treated as derived and disposable;
- CLI commands are covered by tests;
- export excludes `catalog.duckdb`;
- export contains manifest, base Parquet, mart Parquet, artifact Parquet, and
  checksums.

## Issue 12 — Full reporting mart expansion and performance checks

Depends on: Issues 6 and 7.

Scope:

- implement remaining first-pass marts;
- benchmark representative dashboard queries;
- document latency envelopes and known limits.

Definition of done:

- all first-pass marts exist;
- summary queries, capital tree/top-contributor queries, and artifact first-page
  drillthrough have benchmark fixtures;
- performance evidence is recorded in package docs or test artifacts.

## Milestone 1 — Vertical Slice

1. Issue 1
2. Issue 2
3. Issue 3
4. Issue 4

Milestone 1 proves deterministic identity, canonical graph generation, strict
artifact writes, and manifest-led commit atomicity end to end.

## Milestone 2 — Query And Governance Surface

1. Issue 5
2. Issue 6
3. Issue 7
4. Issue 11

## Milestone 3 — Serving, Object Storage, And Scale

1. Issue 9
2. Issue 10
3. Issue 8
4. Issue 12

S3 support can move earlier if object-store deployment becomes mandatory before
the FastAPI service.
