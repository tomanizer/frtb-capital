# frtb-result-store storage contract and operations

This document describes the durable storage contract implemented by
`DuckDbParquetResultStore`. It complements
[DETAILED_DESIGN.md](DETAILED_DESIGN.md) and
[PUBLIC_API.md](PUBLIC_API.md) with operator-facing semantics for writes,
reads, failure handling, and evidence boundaries.

The contract applies to the first DuckDB/Parquet backends (`local_parquet`,
`s3_parquet`). `ducklake` remains reserved and fails closed until explicitly
implemented.

For a runnable public-API handoff from a completed synthetic suite result into a
manifest-gated local store, see
[`packages/frtb-result-store/examples/run_demo.py`](../../../packages/frtb-result-store/examples/run_demo.py).

## Role of the store

The result store persists **calculation evidence** after capital engines finish.
It does not compute regulatory capital, validate business approvals, or decide
whether a run is official for submission.

| The store preserves | The store does not determine |
| --- | --- |
| Immutable run identity and canonical identity payloads | Whether capital numbers are regulatory-correct |
| Capital graph shape, scalar measures, and lineage refs | Whether inputs were complete or approved |
| Artifact references, checksums, and schema fingerprints | Whether attribution is exact Euler decomposition |
| Append-only status history and non-lifecycle events | Whether a run supersedes another for reporting |
| Dashboard marts derived from committed bundle content | Whether marts match an external reporting cube |

Callers remain responsible for calculation correctness upstream. The store fails
closed when persisted evidence would be incomplete, inconsistent, or unreadable.

## Manifest-gated writes

A run is **not readable** until its `run_manifest.json` exists under
`manifests/run_id=<url-encoded-run-id>/`.

Write sequence:

1. Validate the incoming `ResultBundle` and artifact write requests.
2. Stage Parquet for base tables, status events, marts, and artifacts under
   `_staging/<safe-run-id>/`.
3. Validate required artifacts, artifact schema fingerprints, and artifact ref
   targets before any durable publish.
4. Publish staged Parquet and marts into their final paths.
5. Write the run manifest last.

Readers enumerate committed runs only from manifest paths. Parquet files
without a matching manifest are treated as **orphaned** and ignored by queries,
catalog refresh, and list operations.

Rewriting the same `run_id` is forbidden. Corrections require a new calculation
run with a new identity payload and storage id.

## Artifact checksums and schema fingerprints

Large drillthrough payloads live outside scalar measure rows. Each committed
artifact must satisfy:

- a registered artifact schema entry in `ARTIFACT_SCHEMA_REGISTRY`;
- a deterministic `artifact_id` derived from run id, type, partition values,
  schema fingerprint, and optional hint;
- a stored `schema_fingerprint` on the corresponding `ArtifactRef` row;
- a URI that resolves to staged or published Parquet for local backends.

During `write_bundle`, the store validates:

- required and conditional artifact expectations before manifest commit;
- staged artifact schema against the registry fingerprint;
- that every `ArtifactRef` URI target exists at commit time.

Manifests record:

- `base_table_schema_fingerprints` for every base/event table schema;
- sorted `artifact_schema_fingerprints` from committed artifact refs;
- `mart_schema_fingerprints` for every dashboard mart.

Readers reject incompatible runs when any fingerprint in the manifest does not
match the reader's current schema definitions.

## Schema evolution

`RESULT_STORE_SCHEMA_VERSION` (currently `2`) is stored in each manifest as
`schema_version` and `result_store_schema_version`.

Compatible evolution within a version:

- additive nullable Parquet columns when readers use `union_by_name = true`;
- new optional metadata keys on domain objects;
- new mart columns only when mart fingerprints change in a coordinated release.

Breaking evolution requires:

- a new `RESULT_STORE_SCHEMA_VERSION`;
- an ADR documenting migration or dual-read behavior;
- explicit tests that old manifests fail closed or migrate as designed.

The store does not auto-migrate committed runs. Older manifests remain readable
only while their recorded fingerprints still match reader definitions.

## Backend semantics

| Backend | Durable layout | Query path | Notes |
| --- | --- | --- | --- |
| `local_parquet` | Files under configurable `root/` | DuckDB `read_parquet` over manifest-listed files | Default integration mode |
| `s3_parquet` | Logical `s3://bucket/prefix` layout | Same logical layout; local `s3_mock_root` maps URIs for tests | Requires explicit mock root today |
| `ducklake` | Reserved | Not implemented | Constructor raises contract error |

Shared semantics across implemented backends:

- one Parquet file per run per base table;
- status events stored per run under `run_status_events/<safe-run-id>/`;
- artifacts partitioned under `artifacts/artifact_type=.../run_id=.../`;
- marts under `parquet/marts/<mart>/<safe-run-id>.parquet`;
- `catalog.duckdb` is **derived** convenience state, not durable evidence.

S3 has no atomic multi-object rename. Local and S3 backends therefore share the
same manifest-last publish pattern rather than pretending cross-object atomicity.

## Rollback and failure behavior

`write_bundle` wraps staging, publish, and manifest commit in a failure-aware
sequence:

- On any error before manifest commit, moved Parquet, staged artifacts, and
  staged marts are removed.
- Orphan cleanup runs before a retry for the same `run_id`.
- Abandoned staging directories are deleted in `finally`.

After manifest commit:

- catalog refresh failures are logged and swallowed; the run remains committed;
- readers use manifest-gated file lists, not catalog completeness, as truth.

Status transitions after commit are append-only via separate status event
Parquet files. The store does not rewrite historical lifecycle rows.

## Orphaned files and objects

Orphans can appear when a process crashes after publishing Parquet but before
writing the manifest, or when manual filesystem edits occur.

Policy:

| Location | Reader behavior | Writer behavior |
| --- | --- | --- |
| Base/mart Parquet without manifest | Ignored | Removed before retry of same `run_id` |
| Artifacts without manifest | Ignored | Removed before retry of same `run_id` |
| Manifest without Parquet | Run listed but queries fail compatibility checks | N/A |
| Staging under `_staging/` | Ignored | Deleted after success or failure |

Admin `validate_store` reports inconsistencies; it does not silently repair
committed evidence.

## Read-only API boundaries

Three read surfaces exist:

1. **Domain query methods** on `DuckDbParquetResultStore` — preferred programmatic
   access to runs, graphs, measures, artifacts, attribution, lineage, events,
   and marts.
2. **Optional FastAPI app** (`create_result_store_app`) — read-only HTTP
   endpoints over the same domain queries; no write routes; no raw table dump
   endpoints as the primary contract.
3. **Derived catalog** (`read_only_connection`, `refresh_catalog`) — DuckDB
   views over manifest-listed Parquet; rebuildable and not authoritative on its
   own.

Write operations are limited to:

- `write_bundle`;
- append-only status/event writers exposed for lifecycle tooling;
- admin export/validate/refresh helpers that do not mutate committed run
  evidence except by creating new export directories.

The API layer must not share a writable catalog connection with serving paths.

## Operator checklist

Before treating a run as available to dashboards:

1. Confirm `run_manifest.json` exists for the `run_id`.
2. Confirm `validate_store` reports no blocking errors for the root.
3. Confirm lifecycle status history matches operational expectations.
4. Treat capital numbers as engine outputs; use lineage and artifact refs for
   drilldown, not as proof of regulatory approval.

See [BACKEND_ACCEPTANCE_CRITERIA.md](BACKEND_ACCEPTANCE_CRITERIA.md) for the
gate that must pass before enabling a production object-store backend.
