# Dataset Contract

The result-store package owns persisted FRTB calculation evidence after the
capital engines have finished. It does not own raw market-risk input schemas and
does not calculate regulatory capital.

This package's dataset contract is therefore a storage-result contract:

- immutable calculation runs,
- FRTB capital graph nodes and edges,
- scalar capital and intermediate measures,
- input snapshot manifests,
- lineage references,
- attribution records,
- movement records,
- large artifact references and strict artifact Parquet payloads,
- status events, result events, telemetry, and derived dashboard marts.

The detailed operator-facing storage contract is
`docs/modules/frtb-result-store/STORAGE_CONTRACT.md`. This package-local
contract summarizes the data boundary and persisted row families.

## Boundary

`frtb-result-store` preserves calculation evidence. It does not determine:

- whether a capital number is regulatory-correct,
- whether inputs were complete or approved,
- whether a run is official for submission,
- whether attribution is exact Euler decomposition,
- whether one run supersedes another for reporting.

Component packages and orchestration own calculation, validation, and summary
contracts. The result store consumes completed evidence bundles and persists
them append-only.

The canonical write input is `ResultBundle`, optionally accompanied by
`ArtifactWriteRequest` objects for strict Parquet artifacts.

The canonical read contract is domain-specific query access to committed runs,
capital trees, measures, artifacts, attribution, lineage, movements, events, and
marts. The store is not a generic table dump API.

## Result Bundle

`ResultBundle` is the complete append-only payload for one run. It contains:

- `CalculationRun`
- non-empty `CapitalNode` rows
- optional hierarchy definition and hierarchy nodes
- `CapitalEdge` rows
- `CapitalMeasure` rows
- `ArtifactRef` rows
- `InputSnapshotManifest` rows
- `LineageRef` rows
- `CapitalAttributionRecord` rows
- `MovementResult` rows
- `ResultEvent` rows
- `RunTelemetry` rows

All rows in a bundle must carry the bundle run id. Node ids must be unique
within the run. Edges, measures, attributions, and movement rows must reference
known graph or hierarchy nodes where required.

Corrections are represented by a new `run_id`. Rewriting the same run is a hard
write error.

## Base Tables

The durable base table schemas are defined in
`frtb_result_store.store_schemas`. Current run tables are:

- `runs`
- `hierarchy_definitions`
- `hierarchy_nodes`
- `capital_nodes`
- `capital_edges`
- `capital_measures`
- `artifact_refs`
- `artifact_expectations`
- `input_snapshot_manifests`
- `lineage_refs`
- `capital_attributions`
- `movement_results`
- `result_events`
- `run_telemetry`

Lifecycle status history is stored separately in:

- `run_status_events`

`RESULT_STORE_SCHEMA_VERSION` is recorded in every run manifest. Readers reject
committed runs when the manifest schema version or recorded schema fingerprints
do not match the current reader definitions.

## Run Identity

`CalculationRun` carries immutable run identity:

- `run_id`
- `as_of_date`
- `regime_id`
- `base_currency`
- `input_snapshot_id`
- `calculation_scope`
- `engine_version`
- `code_version`
- `calculation_policy_id`
- timezone-aware `created_at`
- optional `run_group_id`
- optional canonical identity payloads and metadata

When identity payloads are supplied, `run_id` and `run_group_id` must match the
canonical hashes generated from those payloads.

## Capital Graph

`CapitalNode` and `CapitalEdge` represent the FRTB drilldown graph. Supported
component labels include:

- `TOP_OF_HOUSE`
- `IMA`
- `SA`
- `SBM`
- `DRC`
- `RRAO`
- `CVA`

Supported node types include root, component, desk, portfolio, book, risk class,
bucket, issuer, counterparty, hedge set, measure branch, risk factor, and
position nodes.

`CapitalMeasure` rows store scalar amounts against nodes. Capital figures are
non-negative evidence values in their declared currency; raw component sign
conventions remain component-owned.

## Input Snapshots And Lineage

`InputSnapshotManifest` records compact upstream input evidence:

- input snapshot id and hash,
- as-of date,
- source system,
- handoff key,
- row counts,
- accepted and rejected row counts,
- optional source URI, source hash, schema fingerprint, and metadata.

`LineageRef` links stored result ids to source ids, hashes, and relationship
labels. These rows preserve audit traceability; they do not validate the
regulatory correctness of upstream inputs.

## Artifacts

Large drillthrough payloads are stored outside scalar measure rows. `ArtifactRef`
records carry:

- artifact id,
- component,
- artifact type,
- URI,
- format,
- row count,
- schema fingerprint,
- partition keys,
- metadata.

`ArtifactWriteRequest` writes strict Parquet artifacts through the registered
artifact schema catalog. Each generated artifact has a deterministic artifact id
derived from run id, artifact type, partition values, schema fingerprint, and an
optional hint.

Current artifact types include IMA P&L vectors and tail observations, SBM
sensitivity and correlation tables, DRC JTD tables, RRAO exposure tables, CVA
exposure tables, attribution vectors, movement explanations, and `OTHER`.

The current strict artifact schema registry contains `ima.pnl_vector.v1`.
Additional artifact refs may be persisted as URI-backed references, but strict
artifact writes must use a registered schema id.

## Attribution And Movements

`CapitalAttributionRecord` stores attribution rows compatible with
`frtb_common.CapitalContribution`. Supported attribution targets include
positions, sensitivities, risk factors, issuers, counterparties, desks,
portfolios, books, residual branches, and unsupported branches.

`MovementResult` stores run-to-run movement explanations and links to optional
artifact drillthrough. The store persists movement evidence; it does not decide
which run is official or superseded for reporting.

## Manifest-Gated Commit

A run is not readable until its `run_manifest.json` exists under the manifest
layout. The write sequence is:

1. Validate the `ResultBundle` and artifact write requests.
2. Stage base tables, status events, marts, and artifacts.
3. Validate required artifacts, artifact schema fingerprints, and artifact ref
   targets.
4. Publish staged Parquet and marts.
5. Write the run manifest last.

Readers discover committed runs from manifests. Orphaned Parquet files or
artifacts without a matching manifest are ignored.

The manifest records:

- result-store schema version,
- writer version,
- backend and root layout,
- run identity fields,
- row counts by table,
- row counts by mart,
- base table schema fingerprints,
- artifact schema fingerprints,
- mart schema fingerprints.

## Backends

Implemented backends are:

- `local_parquet`
- `s3_parquet` with an explicit local mock root for current tests

`ducklake` is reserved and fails closed until implemented.

Both implemented backends use the same logical layout:

- `parquet/base/`
- `parquet/marts/`
- `artifacts/`
- `manifests/`

`catalog.duckdb` is derived convenience state over committed Parquet files. It
can be rebuilt and is not durable evidence.

## Dashboard Marts

Dashboard marts are derived from committed bundle content. Current marts are:

- `capital_summary`
- `capital_tree`
- `top_contributors`
- `movement_summary`
- `regime_comparison`
- `component_breakdown`
- `ima_desk_dashboard`
- `sbm_bucket_ladder`
- `drc_issuer_contributors`
- `cva_counterparty_contributors`
- `rrao_exposure_summary`

Mart schemas and fingerprints are defined in `frtb_result_store.mart_schemas`.
Marts support dashboard queries but do not replace base evidence tables.

## API And Export Boundary

The optional FastAPI service is read-only. It exposes FRTB-specific endpoints
for committed runs, run groups, capital trees, measures, artifacts,
attribution, lineage, events, movements, and regime comparison. It does not
expose write endpoints or generic raw table dumps.

The admin export command writes a one-way evidence bundle containing:

- `run_manifest.json`
- `parquet/base/`
- `parquet/marts/`
- copied local or mock-S3 artifact Parquet under `parquet/artifacts/`
- `checksums.json`

Import, approval workflow, and lifecycle management commands are outside the
current package scope.

## Update Rules

When changing result-store data semantics:

1. Update this contract when a persisted row family, manifest field, artifact
   rule, mart, or backend boundary changes.
2. Update `docs/modules/frtb-result-store/STORAGE_CONTRACT.md` for
   operator-facing storage behavior changes.
3. Update `docs/modules/frtb-result-store/PUBLIC_API.md` when stable symbols or
   query surfaces change.
4. Bump `RESULT_STORE_SCHEMA_VERSION` for breaking persisted schema changes.
5. Add or update tests for write compatibility, manifest fingerprints, export,
   read-only API behavior, and affected marts.
6. Run `make agent-guard` before publishing the branch.

If only row ordering, dictionary ordering, hashes, or generated timestamps
change, treat that as a determinism issue and fix the source of instability
before accepting the update.
