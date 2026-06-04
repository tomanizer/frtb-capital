# frtb-result-store first-pass design

This document records the first-pass target design for the FRTB result store.
It extends the initial DuckDB/Parquet package slice with the storage, API,
artifact, mart, and lifecycle choices needed to serve analysts and reporting
systems.

The result store remains an evidence and serving layer. It does not calculate
IMA, SBM, DRC, RRAO, CVA, SA, or top-of-house capital.

## Scope

The first pass supports:

- immutable FRTB calculation runs;
- firm-to-book business hierarchy drilldown;
- component, risk-class, bucket, issuer, and counterparty drilldown;
- strict, store-written Parquet artifacts for deep sensitivity, position,
  source-row, scenario, and exposure drillthrough;
- Euler, residual, and unsupported attribution records across multiple target
  levels;
- first-class movement analysis;
- persisted reporting marts;
- Python write/query APIs;
- read-only FastAPI service;
- best-effort read-only DuckDB SQL access for power users;
- deterministic single-run export.

Out of scope for the first pass:

- capital calculation formulae;
- approval workflow engine;
- access-control enforcement;
- SQLAlchemy abstraction;
- DuckLake implementation;
- import of run exports;
- deletion, hiding, or artifact deduplication.

## Business Hierarchy

The default store hierarchy uses `book_id` as the lowest collection of trades
or positions:

```text
firm -> legal entity -> business line -> desk -> portfolio -> book
```

The result store stores these dimensions on result nodes and marts. User,
role, and entitlement checks are owned by the API/auth layer above the store,
not by the storage layer.

Hierarchy management is separate from FRTB capital-node management. The default
hierarchy above is provided out of the box, but clients may define additional
business or risk-management hierarchy levels and aggregation nodes. The FRTB
capital graph attaches to the resolved hierarchy path at the configured leaf,
which is `book_id` by default.

## Run Identity And Lifecycle

`run_id` is generated deterministically by the result store from:

```text
as_of_date
regime_id
calculation_scope
input_snapshot_id
calculation_policy_id
engine_version
code_version
```

`run_id` uses the full `frtb_common.hashing.stable_json_hash` digest of the
canonical identity payload. Human-readable external batch references and short
hash prefixes may be stored separately, but `run_id` is an opaque stable
machine identifier. Prefix lookup must fail closed when a prefix is ambiguous.
Re-committing an existing `run_id` is rejected; supersession is represented by a
lifecycle event, not overwrite.

Regime comparison uses a linked `run_group_id`. Each child run remains
regime-specific and immutable:

```text
run_group_id
  BASEL_MAR
  US_NPR_2_0
  EU_CRR3
  PRA_UK_CRR
```

Run retention is indefinite. Official runs, candidate runs, intraday reruns,
restatements, and comparison runs are append-only evidence.

Lifecycle status is append-only event data, not a mutable field:

```text
CANDIDATE
VALIDATED
OFFICIAL
SUPERSEDED
REJECTED
```

Status events contain:

```text
event_id
run_id
from_status
to_status
event_time
actor
reason_code
reason_text
external_evidence_ref optional
```

Approval comments, signoffs, human workflow tasks, and model validation review
state live outside the result store. The store may expose a suggested status
from result events, but it does not enforce workflow.

## Capital Graph

The result store generates canonical node IDs and standard graph edges from
normalized node dimensions. Callers provide dimensions and measures; they do
not provide arbitrary node IDs or graph edges.

Standard graph shape:

```text
hierarchy graph
  firm
    legal entity
      business line
        desk
          portfolio
            book
              capital graph
                component
                  risk class
                    bucket
                      issuer / counterparty / branch
```

The hierarchy graph is configurable. The FRTB capital graph under each resolved
hierarchy leaf remains standardized so capital aggregation remains
deterministic. Unsupported or residual cases are represented through
attribution and event records, not custom capital-calculation branches.

Drilldown depth:

- capital graph to bucket, issuer, and counterparty;
- sensitivity, position, and source-row detail through Parquet artifacts.

## Measures And Currency

Dashboard aggregation uses the run base currency. Measures may also preserve
native-currency detail where needed:

```text
base_amount
base_currency
native_amount optional
native_currency optional
fx_rate optional
fx_rate_id optional
fx_source_hash optional
```

Regulatory citations are stored at policy/profile level and on nodes or
measures where the stored number depends on a cited rule. Structural rows do
not repeat citations unnecessarily.

## Artifacts

The result store physically writes large artifacts. Callers provide chunked
payloads; the store validates schemas, writes Parquet, records fingerprints,
and commits artifact references as part of the run commit.

Artifact writes are chunked/streaming-first. Base result tables remain bundled
in memory and written atomically per run.

Artifact commit flow:

```text
write_bundle(...)
  stage base tables
  stage artifact chunks
  validate required artifact schemas
	  write persisted marts
	  commit run manifest
```

Missing required artifacts reject the run commit. The store must not commit a
run with incomplete drillthrough evidence. The run manifest is the commit
marker for both local and future S3 layouts; readers ignore staged or orphaned
Parquet objects that are not referenced by a committed manifest.

Artifacts are required by component/result type:

| Component present | Required artifacts |
| --- | --- |
| IMA | `IMA_PNL_VECTOR`; `IMA_TAIL_OBSERVATION` when `IMA_ES_TAIL_EVIDENCE` is declared |
| SBM | `SBM_SENSITIVITY_TABLE`; `SBM_CORRELATION_INPUT` when `SBM_SCENARIO_SELECTION_EVIDENCE` is declared |
| DRC | `DRC_JTD_TABLE` |
| RRAO | `RRAO_EXPOSURE_TABLE` |
| CVA | `CVA_EXPOSURE_TABLE` |

Artifacts are written per run. There is no first-pass content-addressed
deduplication.

Default compression is ZSTD. Store-managed encryption is out of scope; local
disk controls or S3/KMS own encryption.

## Artifact Schemas

Artifact schemas are strict by artifact type. The store validates required
columns, logical types, nullability, stable identifiers, and schema
fingerprints before writing Parquet.

IMA P&L vector first-pass schema:

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

Partitioning:

```text
common:
  as_of_date / regime_id / run_id / artifact_type

IMA:
  desk_id / portfolio_id / book_id

SBM:
  risk_class / bucket

DRC:
  bucket / issuer_id

CVA:
  counterparty_id

RRAO:
  residual_risk_type or exposure_category
```

## Attribution

Attribution supports multiple target levels from the first pass:

```text
position
sensitivity
risk_factor
issuer
counterparty
desk
portfolio
book
residual_branch
unsupported_branch
```

Rows record:

```text
target_type
target_id
source_level
method
category
bucket_key
amount
marginal_multiplier optional
residual
unsupported_reason optional
artifact_ref optional
```

This keeps Euler attribution compatible with SBM/IMA risk-factor analysis and
position-level desk explanation.

## Movement Analysis

Movement analysis is first-class stored result data, not only an on-demand
comparison query.

Movement rows contain:

```text
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
artifact_ref optional
```

Supported movement use cases include day-over-day, rerun-over-rerun, and
regime-over-regime comparisons.

## Events And Status Suggestions

The result store has a separate event stream for data quality and calculation
warnings:

```text
result_event
  event_id
  run_id
  node_id optional
  artifact_id optional
  severity
  event_type
  event_code
  message
  source_system optional
  source_id optional
  created_at
```

Event types:

```text
DATA_QUALITY
CALCULATION_WARNING
UNSUPPORTED_FEATURE
SCHEMA_WARNING
STORE_WRITE_WARNING
VALIDATION_WARNING
```

Events can produce an advisory `suggested_status`, for example `REJECTED` when
error-level events exist, but warnings remain event metadata and do not create a
`VALIDATED_WITH_WARNINGS` lifecycle status.

## Marts

Hot analyst and reporting queries read persisted Parquet marts, not raw vector
artifacts.

The first-pass mart set is:

```text
capital_summary
capital_tree
top_contributors
residual_attribution
unsupported_attribution
movement_summary
regime_comparison
component_breakdown
ima_desk_dashboard
sbm_bucket_ladder
drc_issuer_contributors
cva_counterparty_contributors
rrao_exposure_summary
```

Marts are persisted as Parquet under:

```text
parquet/marts/<mart-name>/
```

Mart schemas carry schema versions and fingerprints.

Performance targets:

```text
summary queries: < 200ms
capital tree / top contributors: < 500ms
artifact drillthrough first page: < 2s
```

## Storage Backends

First-pass deployment modes:

```text
local filesystem
S3-backed Parquet paths
```

DuckLake remains designed-for but not implemented in the first pass.

The backend uses Parquet files as durable storage and DuckDB as an optional
query engine. SQLAlchemy is not used because the first-pass portability concern
is Parquet/object-storage layout, artifact partitioning, and DuckDB/DuckLake
semantics rather than relational database dialect switching. Read services
should use their own read-only or in-memory DuckDB connection over committed
manifests and Parquet files rather than sharing a mutable writer catalog.

Schema governance includes:

```text
schema_version
table_schema_fingerprint
artifact_schema_fingerprint
mart_schema_fingerprint
writer_version
per-run reader compatibility check
```

The first pass is single-run atomic. Multi-run regime-group atomic commits are
out of scope.

## APIs

The package exposes a Python API and a read-only FastAPI service.

Backend, serving, and observability dependencies are optional at dependency
level:

```text
[project.optional-dependencies]
duckdb = ["duckdb>=1.4,<2"]
otel = ["opentelemetry-api>=1,<2"]
api = ["fastapi", "uvicorn"]
```

The HTTP API exposes FRTB-specific resources only. It does not expose a generic
raw-table dump API.

OpenAPI tags:

```text
Runs
Run Groups
Capital Tree
IMA
SBM
DRC
RRAO
CVA
Movements
Regime Comparison
Artifacts
Attribution
Lineage
Events
Exports
```

Artifact drillthrough supports both:

- paged JSON rows for webapp grids;
- downloadable Parquet for bulk analysis.

There is no first-pass generated client SDK. Consumers use OpenAPI, the
FastAPI service, or the local Python API.

## SQL Access

The official API contract is the Python API, FastAPI endpoints, and documented
response schemas.

The store also exposes a best-effort read-only DuckDB connection helper for
power users. Raw SQL table and view names may change between versions and are
not the primary compatibility contract.

## CLI

The first pass includes a small admin CLI:

```text
frtb-result-store inspect <root>
frtb-result-store list-runs <root>
frtb-result-store refresh-catalog <root>
frtb-result-store export-run <root> <run-id> <output-path>
frtb-result-store validate-store <root>
```

Lifecycle/status writes stay in trusted Python APIs, not the read-only HTTP
service.

## Export

Single-run export is supported. Import is out of scope.

Export package:

```text
run_export/
  run_manifest.json
  parquet/
    base tables for run
    marts for run
    artifacts for run
  checksums.json
```

`catalog.duckdb` is excluded because the catalog can be rebuilt from Parquet
files and manifests.

## Input Snapshot Manifest

The result store records compact input snapshot manifests, not full upstream
input copies:

```text
input_snapshot_id
input_snapshot_hash
as_of_date
source_system
handoff_key
row_count
accepted_row_count
rejected_row_count
source_uri optional
source_hash
schema_fingerprint
```

Result lineage can point to these manifest entries.

## Telemetry

Compact run telemetry is stored for performance evidence:

```text
run_telemetry
  run_id
  trace_id optional
  span_id optional
  phase
  duration_ms
  row_count optional
  byte_count optional
  artifact_id optional
  mart_name optional
  created_at
```

The result store should use OpenTelemetry for runtime traces and metrics when
the optional `opentelemetry-api` dependency is installed. Standard logging may
carry trace context where available. Persisted `run_telemetry` rows are compact
audit/performance summaries derived from store phases, not a replacement for
OpenTelemetry traces. SDK, collector, and exporter configuration belongs to the
application or FastAPI service deployment. If OpenTelemetry is absent,
instrumentation degrades to no-op behavior.

Initial phases:

```text
BASE_TABLE_WRITE
ARTIFACT_WRITE
MART_GENERATION
CATALOG_REFRESH
EXPORT
```

## Next Implementation Sequence

1. Add deterministic `run_id` / `run_group_id` generation and append-only
   status events.
2. Add configurable hierarchy management, default book-level hierarchy, and
   standardized capital-node generation.
3. Add strict artifact schemas and chunked artifact write requests.
4. Add required-artifact validation during `write_bundle`.
5. Add persisted Parquet marts for `capital_summary`, `capital_tree`, and
   `component_breakdown`, then expand to the full mart set.
6. Add read-only FastAPI endpoints over runs, capital tree, artifacts,
   attributions, lineage, events, and movements.
7. Add one-way single-run export and compact input snapshot manifests.
