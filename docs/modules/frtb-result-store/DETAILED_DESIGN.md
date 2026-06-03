# frtb-result-store detailed design

This document turns the first-pass result-store target into an implementation
design. It is intentionally FRTB-specific and should be read with
[FIRST_PASS_DESIGN.md](FIRST_PASS_DESIGN.md).

## Design Goals

The result store must:

- persist immutable FRTB calculation evidence;
- serve low-latency analyst and reporting queries;
- preserve drillthrough to IMA vectors, SBM sensitivities, DRC JTD rows, RRAO
  exposures, and CVA exposure data;
- keep capital kernels free of storage dependencies;
- support deterministic run, graph, artifact, attribution, movement, and mart
  identifiers;
- support local filesystem and S3 Parquet layouts before DuckLake;
- expose FRTB-specific APIs rather than raw storage tables as the primary
  contract.

The result store must not:

- calculate capital;
- own approval workflow, entitlements, or signoffs;
- depend on capital component packages;
- rely on SQLAlchemy for the DuckDB/Parquet backend;
- commit runs with missing required drillthrough evidence.

## Package Boundary

Runtime dependency direction:

```text
frtb-result-store core
  -> frtb-common

frtb-result-store DuckDB/Parquet backend
  -> frtb-common
  -> third-party IO/query libraries: duckdb, pyarrow

frtb-result-store observability instrumentation
  -> optional opentelemetry-api
```

No dependency:

```text
frtb-result-store -> frtb-orchestration
frtb-result-store -> frtb-ima / frtb-sbm / frtb-drc / frtb-rrao / frtb-cva
capital packages -> frtb-result-store
```

Callers convert component or orchestration outputs into neutral
`frtb-result-store` DTOs outside the result-store core. A future adapter package
or application layer may own that projection.

## Storage Layout

First-pass durable layout:

```text
result-store-root/
  catalog.duckdb
  manifests/
    run_id=<run-id>/run_manifest.json
  parquet/
    base/
      runs/
      run_status_events/
      run_groups/
      input_snapshot_manifests/
      hierarchy_definitions/
      hierarchy_nodes/
      hierarchy_edges/
      capital_nodes/
      capital_edges/
      capital_measures/
      artifact_refs/
      lineage_refs/
      capital_attributions/
      movement_results/
      result_events/
      run_telemetry/
    artifacts/
      artifact_type=<type>/
        as_of_date=<date>/
        regime_id=<regime>/
        run_id=<run-id>/
        ...
    marts/
      capital_summary/
      capital_tree/
      top_contributors/
      movement_summary/
      regime_comparison/
      component_breakdown/
      ima_desk_dashboard/
      sbm_bucket_ladder/
      drc_issuer_contributors/
      cva_counterparty_contributors/
      rrao_exposure_summary/
```

Each committed run has exactly one run manifest. The manifest is the commit
marker. Readers discover committed runs from manifests and ignore any staged or
orphaned Parquet object that is not referenced by a committed manifest.

The DuckDB catalog is derived from Parquet files and can be rebuilt. The
catalog is not included in run exports. Read services should open their own
read-only or in-memory DuckDB connection over committed manifests and Parquet
files rather than sharing a mutable writer catalog across processes.

S3 mode uses the same logical path layout under an `s3://` root. DuckDB access
uses `httpfs` configuration, but result-store domain code should remain URI
based. S3 has no atomic multi-object rename, so the local and S3 backends share
the same manifest-led commit protocol: stage objects first, write the manifest
last, and garbage-collect abandoned staging objects separately.

## Run Identity

The store generates `run_id` deterministically from a canonical JSON payload:

```text
as_of_date
regime_id
calculation_scope
input_snapshot_id
calculation_policy_id
engine_version
code_version
```

Storage ID format:

```text
run:<sha256>
```

where the hash is `frtb_common.hashing.stable_json_hash` of the canonical
identity payload. Short prefixes may be shown as display aliases, but full
digests are storage identifiers. A lookup by prefix must fail closed if the
prefix maps to more than one stored identity payload. The full identity payload
is stored on the run row and in the run manifest.

Re-committing an existing `run_id` is rejected. A failed staging attempt may be
retried only when no committed manifest exists for that `run_id`. Supersession
is represented by a lifecycle status event, not by overwriting an existing run.

`run_group_id` is generated from:

```text
as_of_date
calculation_scope
input_snapshot_id
calculation_policy_group_id
engine_version
code_version
group_purpose
```

Each regime-specific run stores the same `run_group_id` when it is part of a
comparison group.

## Run Lifecycle

Runs are immutable. Lifecycle is append-only event data:

```text
run_status_event
  event_id
  run_id
  from_status
  to_status
  event_time
  actor
  reason_code
  reason_text
  external_evidence_ref
```

Allowed statuses:

```text
CANDIDATE
VALIDATED
OFFICIAL
SUPERSEDED
REJECTED
```

The first event for a committed run is `CANDIDATE`. Promotion to `VALIDATED` or
`OFFICIAL` is written through trusted Python APIs. The read-only FastAPI service
does not mutate status.

Latest status is derived from events and materialized into marts for fast API
queries.

Result-event-derived status is advisory only. It must be named
`suggested_status` in APIs and marts so it cannot be confused with lifecycle
status written by trusted status APIs.

## Hierarchy Management

Hierarchy management is separate from FRTB capital-node management. The result
store provides a default business hierarchy, but clients may define additional
business or risk-management hierarchy levels and aggregation nodes without
changing the FRTB capital graph model.

Default hierarchy:

```text
firm -> legal_entity -> business_line -> desk -> portfolio -> book
```

`book_id` is the lowest default collection of trades or positions.

Hierarchy definition rows:

```text
hierarchy_definition
  hierarchy_id
  hierarchy_version
  hierarchy_name
  leaf_level
  levels_json
  created_at
  metadata_json
```

Hierarchy node rows:

```text
hierarchy_node
  hierarchy_id
  hierarchy_version
  hierarchy_node_id
  parent_hierarchy_node_id
  level_name
  level_order
  business_key
  label
  metadata_json
```

Default hierarchy dimensions:

```text
firm_id
legal_entity_id
business_line_id
desk_id
portfolio_id
book_id
```

The capital graph attaches to a resolved hierarchy leaf. The default leaf is
`book_id`. Client-defined hierarchy levels are allowed above, below, or beside
the default levels when a `HierarchyDefinition` declares their order and leaf.
The result store must preserve deterministic hierarchy paths and node IDs.

## FRTB Capital Nodes

FRTB capital nodes are standardized under the resolved hierarchy leaf.
Capital nodes may carry:

```text
component
risk_class
risk_measure
bucket
issuer_id
counterparty_id
hedge_set_id
residual_risk_type
calculation_branch
regulatory_rule_id
```

The result store stores these identifiers and labels but does not enforce user
entitlements.

## Canonical Node And Edge Generation

Callers submit normalized hierarchy paths, FRTB capital node dimensions, and
measures. The store generates canonical hierarchy node IDs, capital node IDs,
and graph edges.

Canonical node IDs are generated from structured identity payloads, not from
raw colon-joined strings. The stored ID format is:

```text
<node-family>:<stable-json-hash>
```

Human-readable aliases may use percent-encoded path fragments, but aliases are
not storage keys.

Canonical text normalization:

- reject empty strings for identity fields;
- normalize Unicode strings to NFC;
- preserve business-key case unless a controlled FRTB vocabulary requires a
  specific enum value;
- serialize dates as ISO `YYYY-MM-DD`;
- serialize datetimes as timezone-aware ISO strings;
- use `frtb_common.hashing.stable_json_hash` for every canonical node,
  artifact, schema, manifest, and mart fingerprint.

Node ID inputs:

| Node family | Required identity payload fields |
| --- | --- |
| `hierarchy` | `hierarchy_id`, `hierarchy_version`, `level_name`, ordered normalized path from root to this node |
| `component` | `hierarchy_leaf_path`, `component`, optional `calculation_branch` |
| `risk_class` | `hierarchy_leaf_path`, `component`, `risk_class`, optional `risk_measure`, optional `calculation_branch` |
| `bucket` | `hierarchy_leaf_path`, `component`, `risk_class`, optional `risk_measure`, `bucket`, optional `calculation_branch` |
| `issuer` | `hierarchy_leaf_path`, `component`, `risk_class`, `bucket`, `issuer_id`, optional `calculation_branch` |
| `counterparty` | `hierarchy_leaf_path`, `component`, `counterparty_id`, optional `hedge_set_id`, optional `calculation_branch` |
| `residual_branch` | `hierarchy_leaf_path`, `component`, `residual_risk_type`, optional `exposure_category`, optional `calculation_branch` |
| `risk_factor` | `hierarchy_leaf_path`, `component`, `risk_factor_id`, optional `risk_factor_set_id`, optional `calculation_branch` |
| `position` | `hierarchy_leaf_path`, `component`, `position_id`, optional `calculation_branch` |

Fields not listed for a node family are attributes, labels, filters, or lineage
fields. They do not participate in ID generation unless the registry for that
node family is revised with a new schema version.

The generator must:

- produce identical hierarchy IDs for identical hierarchy definitions and
  business dimensions across runs;
- produce identical capital node IDs for identical FRTB dimensions under the
  same normalized hierarchy leaf path across runs and hierarchy versions;
- reject missing required dimensions for a node type;
- normalize identity payloads deterministically;
- generate hierarchy edges from the active hierarchy definition;
- generate standardized FRTB capital edges under the resolved hierarchy leaf.

`hierarchy_leaf_node_id` is stored as graph attachment metadata and used for
edges from the active hierarchy tree. It is not an ID-bearing capital payload
field because hierarchy node IDs include `hierarchy_version`.

Standard edge generation:

```text
hierarchy_definition levels -> hierarchy leaf
hierarchy leaf -> component
component -> risk_class
risk_class -> bucket
bucket -> issuer / counterparty / residual branch
```

Custom business hierarchy levels are allowed through `HierarchyDefinition`.
Custom FRTB capital-calculation branches are not allowed in first pass.

## Controlled Vocabularies

The store must avoid free-text drift for repeated analytical fields.

First-pass registries:

```text
measure_name
target_type
movement_type
driver_type
result_event.severity
result_event.event_type
run_status
artifact_type
component
node_type
```

The registry may be implemented as enums for stable fields and as versioned
schema registry entries for fields that need extension by component packages or
client deployments. Unknown values fail closed unless a registry entry declares
the value before write.

## Measure Model

Measures store base-currency values and optional native-currency lineage:

```text
capital_measure
  run_id
  node_id
  measure_name
  base_amount
  base_currency
  native_amount
  native_currency
  fx_rate
  fx_rate_id
  fx_source_hash
  scenario
  methodology
  regulatory_rule_id
  citations_json
  metadata_json
```

Capital dashboards aggregate `base_amount`. Native-currency fields are
drilldown/audit fields and must not be silently aggregated without explicit
conversion.

## Artifact Write Model

Artifacts are written by the result store as part of `write_bundle`.

Writer DTO:

```text
ArtifactWriteRequest
  artifact_id_hint
  artifact_type
  component
  schema_id
  chunks
  partition_values
  required
  metadata
```

Run-level artifact expectations:

```text
RequiredArtifactExpectation
  component
  artifact_type
  trigger_name
  required
  reason
```

The chunk source is streaming-first:

```python
Iterable[pyarrow.Table]
```

The writer:

1. validates every chunk against the strict artifact schema;
2. writes chunked Parquet to a run staging area with ZSTD compression;
3. tracks row count, byte count, partition values, and schema fingerprint;
4. records an `ArtifactRef`;
5. fails the full run commit if a required artifact is missing or invalid.

Committed runs must not reference missing artifacts.

## Required Artifact Rules

Base required artifacts are inferred from components present in the capital
graph. Conditional requirements are driven by explicit
`RequiredArtifactExpectation` rows supplied with the write bundle; the store
validates declared expectations before writing the committed manifest.

| Component | Required artifact types |
| --- | --- |
| IMA | `IMA_PNL_VECTOR`; `IMA_TAIL_OBSERVATION` when `IMA_ES_TAIL_EVIDENCE` is declared |
| SBM | `SBM_SENSITIVITY_TABLE`; `SBM_CORRELATION_INPUT` when `SBM_SCENARIO_SELECTION_EVIDENCE` is declared |
| DRC | `DRC_JTD_TABLE` |
| RRAO | `RRAO_EXPOSURE_TABLE` |
| CVA | `CVA_EXPOSURE_TABLE` |

Missing required artifacts raise before the committed manifest is written.

## Artifact Schema Registry

The store owns a registry of strict artifact schemas. Each schema has:

```text
schema_id
artifact_type
schema_version
arrow_schema
required_columns
nullable_columns
partition_columns
schema_fingerprint
```

Initial schemas:

- IMA P&L vector;
- IMA tail observations;
- SBM sensitivity table;
- SBM correlation inputs;
- DRC JTD table;
- RRAO exposure table;
- CVA exposure table;
- attribution vector;
- movement explanation.

IMA P&L vector columns:

```text
run_id
desk_id
portfolio_id
book_id
position_id
risk_factor_id
risk_factor_set_id
scenario_id
observation_date
liquidity_horizon
pnl_amount
currency
tail_flag
source_row_id
```

## Attribution

Attribution rows support several targets:

```text
POSITION
SENSITIVITY
RISK_FACTOR
ISSUER
COUNTERPARTY
DESK
PORTFOLIO
BOOK
RESIDUAL_BRANCH
UNSUPPORTED_BRANCH
```

Stored fields:

```text
run_id
node_id
attribution_id
target_type
target_id
source_level
method
category
bucket_key
base_amount
marginal_multiplier
contribution
residual
unsupported_reason
artifact_id
metadata_json
```

`frtb_common.CapitalContribution` remains the shared contribution DTO. The
result store extends storage rows with node, target, artifact, and lifecycle
context.

Projection from `CapitalContribution` is explicit:

| `CapitalContribution` field | Attribution storage field |
| --- | --- |
| `contribution_id` | `attribution_id` |
| `source_id` | `target_id` unless an explicit target override is supplied |
| `source_level` | `source_level` and default `target_type` |
| `category` | `category` |
| `bucket_key` | `bucket_key` |
| `base_amount` | `base_amount` |
| `method` | `method` |
| `marginal_multiplier` | `marginal_multiplier` |
| `contribution` | `contribution` |
| `residual` | `residual` |
| `reason` | `unsupported_reason` when the row represents residual or unsupported attribution |

## Movement Results

Movement results are materialized and queryable:

```text
movement_result
  run_id
  baseline_run_id
  movement_id
  node_id
  movement_type
  from_amount
  to_amount
  delta_amount
  base_currency
  driver_type
  driver_id
  explanation
  attribution_method
  artifact_id
```

Official movement analyses are written after a run completes. Ad hoc
comparison APIs can come later, but official dashboards read persisted movement
results.

## Result Events And Status Suggestions

Events are separate from lifecycle status:

```text
result_event
  event_id
  run_id
  node_id
  artifact_id
  severity
  event_type
  event_code
  message
  source_system
  source_id
  created_at
```

Severity:

```text
INFO
WARNING
ERROR
```

Event type:

```text
DATA_QUALITY
CALCULATION_WARNING
UNSUPPORTED_FEATURE
SCHEMA_WARNING
STORE_WRITE_WARNING
VALIDATION_WARNING
```

The store exposes an advisory `suggested_status`:

- `REJECTED` if error-level events exist;
- `VALIDATED` if no error-level events exist;
- warnings remain event summaries and do not create a separate status.

`suggested_status` is not a lifecycle status event and does not promote a run.

## Marts

Marts are persisted Parquet outputs and have stable schema fingerprints.

Initial implementation order:

1. `capital_summary`
2. `capital_tree`
3. `component_breakdown`
4. `top_contributors`
5. `movement_summary`
6. `regime_comparison`
7. component-specific marts

Full first-pass mart set:

```text
capital_summary
capital_tree
top_contributors
movement_summary
regime_comparison
component_breakdown
ima_desk_dashboard
sbm_bucket_ladder
drc_issuer_contributors
cva_counterparty_contributors
rrao_exposure_summary
```

Marts are regenerated on run commit and may be regenerated by the admin CLI.

## Schema Compatibility

Every run manifest records:

```text
result_store_schema_version
writer_version
base_table_schema_fingerprints
artifact_schema_fingerprints
mart_schema_fingerprints
```

Readers check compatibility per run before returning data. Full migration
tooling is out of scope for first pass; an incompatible run fails closed with a
clear compatibility error while other compatible runs in the same archive remain
readable.

## Input Snapshot Manifests

The store records compact input snapshot evidence:

```text
input_snapshot_manifest
  input_snapshot_id
  input_snapshot_hash
  as_of_date
  source_system
  handoff_key
  row_count
  accepted_row_count
  rejected_row_count
  source_uri
  source_hash
  schema_fingerprint
```

Lineage records may reference these manifest rows rather than raw input data.

## Telemetry And OpenTelemetry

The result store should use OpenTelemetry for runtime traces and metrics where
the optional `opentelemetry-api` dependency is installed. Standard logging may
carry trace context where available. SDK, collector, exporter, sampling, and
backend configuration belong to applications and deployments. If
OpenTelemetry is absent, instrumentation must degrade to no-op behavior and
core imports must still work.

Compact persisted run telemetry supports audit/performance evidence and links
to OpenTelemetry trace context where available:

```text
run_telemetry
  run_id
  trace_id
  span_id
  phase
  duration_ms
  row_count
  byte_count
  artifact_id
  mart_name
  created_at
```

Initial phases:

```text
BASE_TABLE_WRITE
ARTIFACT_WRITE
MART_GENERATION
CATALOG_REFRESH
EXPORT
```

Recommended span names:

```text
frtb_result_store.write_bundle
frtb_result_store.write_artifact
frtb_result_store.generate_marts
frtb_result_store.refresh_catalog
frtb_result_store.export_run
```

Recommended low-cardinality span attributes:

```text
frtb.run_id
frtb.regime_id
frtb.as_of_date
frtb.component
frtb.artifact_type
frtb.mart_name
```

Do not emit high-cardinality source-row, position, or risk-factor IDs as
metrics labels. Those identifiers belong in persisted artifacts and lineage,
not metric dimensions.

## Python API

Writer APIs:

```text
generate_run_id(...)
generate_run_group_id(...)
write_bundle(...)
append_status_event(...)
export_run(...)
refresh_catalog(...)
validate_store(...)
```

Query APIs:

```text
list_runs(...)
get_run(...)
latest_status(...)
capital_tree(...)
child_nodes(...)
measures_for_node(...)
artifact_refs(...)
artifact_page(...)
attributions_for_node(...)
lineage_for_result(...)
events_for_run(...)
movement_summary(...)
regime_comparison(...)
read_only_connection(...)
```

## FastAPI Service

The service is read-only and optional. Core package import must not require
FastAPI.

Primary endpoints:

```text
GET /runs
GET /run-groups
GET /runs/{run_id}
GET /runs/{run_id}/capital-tree
GET /runs/{run_id}/nodes/{node_id}
GET /runs/{run_id}/nodes/{node_id}/children
GET /runs/{run_id}/nodes/{node_id}/measures
GET /runs/{run_id}/nodes/{node_id}/attribution
GET /runs/{run_id}/nodes/{node_id}/lineage
GET /runs/{run_id}/events
GET /runs/{run_id}/movements
GET /runs/{run_id}/artifacts
GET /runs/{run_id}/artifacts/{artifact_id}/page
GET /runs/{run_id}/artifacts/{artifact_id}/download
GET /run-groups/{run_group_id}/regime-comparison
```

OpenAPI tags are FRTB-oriented: Runs, Run Groups, Capital Tree, IMA, SBM, DRC,
RRAO, CVA, Movements, Regime Comparison, Artifacts, Attribution, Lineage,
Events, and Exports.

## CLI

First-pass admin CLI:

```text
frtb-result-store inspect <root>
frtb-result-store list-runs <root>
frtb-result-store refresh-catalog <root>
frtb-result-store export-run <root> <run-id> <output-path>
frtb-result-store validate-store <root>
```

The CLI does not own approvals or lifecycle workflow.

## Export

Single-run export writes:

```text
run_export/
  run_manifest.json
  parquet/
    base/
    marts/
    artifacts/
  checksums.json
```

`catalog.duckdb` is excluded. Import is out of scope.

## Implementation Phases

1. Canonical identity, run groups, and status events.
2. Hierarchy management, default book-level hierarchy, and standardized
   capital graph generation.
3. Artifact schema registry and chunked artifact writer.
4. Required-artifact validation and single-run commit staging.
5. Schema compatibility, input manifests, events, and OpenTelemetry.
6. Persisted marts.
7. Movement and attribution storage expansion.
8. S3 Parquet backend mode.
9. FastAPI read service.
10. Read-only SQL helper, admin CLI, and one-way export.
