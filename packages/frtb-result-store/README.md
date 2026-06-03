# frtb-result-store

DuckDB/Parquet result-store package for FRTB capital evidence.

The package persists immutable calculation runs, capital result graph nodes,
scalar measures, lineage references, attribution records, and large-artifact
references. It is storage and serving infrastructure only; capital formulae
remain in the IMA, SBM, DRC, RRAO, CVA, and orchestration packages.

Current runtime support is deliberately narrow:

- append-only `CalculationRun` bundles;
- FRTB-specific `CapitalNode` and `CapitalEdge` graph drilldown;
- scalar `CapitalMeasure` rows for capital and intermediate amounts;
- `ArtifactRef` rows for IMA P&L vectors, ES tail observations, SBM
  sensitivities, DRC JTD tables, CVA exposures, attribution vectors, and
  movement explanations;
- `CapitalAttributionRecord` rows compatible with
  `frtb_common.CapitalContribution`;
- manifest-gated local and S3-layout Parquet files queried through independent
  DuckDB connections;
- best-effort read-only SQL helper and admin CLI for inspection, disposable
  catalog refresh, validation, and one-way run export;
- optional read-only FastAPI service via `frtb-result-store[api]`.

S3 Parquet mode accepts an `s3://bucket[/prefix]` root and keeps the same
logical `parquet/`, `artifacts/`, and `manifests/` layout as local mode. Runs
are still discovered only from committed run manifests, so staged or orphaned
objects remain invisible to readers. Local integration tests and development
can use `ResultStoreConfig(..., backend=StorageBackend.S3_PARQUET,
s3_mock_root=...)`; artifact refs and manifest paths retain the logical
`s3://` URI while Parquet bytes are written to the mock root. DuckDB `httpfs`
and S3 credentials are configured only through `duckdb_extensions`,
`duckdb_install_extensions`, and `duckdb_settings`; the package does not
hard-code credentials.

DuckLake remains an explicit reserved backend mode.

`catalog.duckdb` is derived convenience state over committed Parquet files. It
can be deleted and rebuilt with `DuckDbParquetResultStore.refresh_catalog()` or
`frtb-result-store refresh-catalog <root>`; it is not durable evidence and is
excluded from exports. `DuckDbParquetResultStore.read_only_connection()` opens
that derived catalog with DuckDB read-only mode after refreshing it when needed.

The admin CLI emits JSON for each command:

```text
frtb-result-store inspect <root>
frtb-result-store list-runs <root>
frtb-result-store refresh-catalog <root>
frtb-result-store export-run <root> <run-id> <output-path>
frtb-result-store validate-store <root>
```

`export-run` writes a one-way evidence bundle containing `run_manifest.json`,
`parquet/base/`, `parquet/marts/`, copied local or mock-S3 artifact Parquet under
`parquet/artifacts/`, and `checksums.json`. Import, approval, and lifecycle
workflow commands are intentionally not provided.

First-pass persisted marts are generated for `capital_summary`, `capital_tree`,
`top_contributors`, `movement_summary`, `regime_comparison`,
`component_breakdown`, `ima_desk_dashboard`, `sbm_bucket_ladder`,
`drc_issuer_contributors`, `cva_counterparty_contributors`, and
`rrao_exposure_summary`. The package test
`test_representative_dashboard_query_latency_fixture` records representative
latency envelopes for local synthetic data: summary, capital tree, and
top-contributor mart reads are expected below 250 ms, while artifact first-page
drillthrough is expected below 1000 ms. These are local first-pass envelopes,
not production SLOs; large object-store artifacts, cold DuckDB extension loads,
remote storage latency, and analyst concurrency are outside the benchmark
fixture.

The FastAPI service is created with `create_result_store_app(...)`. It exposes
FRTB-specific read endpoints for runs, run groups, capital trees, measures,
artifacts, attribution, lineage, events, movements, and regime comparison. It
also supports artifact drillthrough with deterministic Parquet-backed pages:
`GET /runs/{run_id}/artifacts/{artifact_id}/page` accepts `limit`, `offset`,
repeated or comma-separated `columns`, and repeated `filter=column=value`
parameters. `GET /runs/{run_id}/artifacts/{artifact_id}/download` serves local
Parquet artifacts directly and returns an S3 URI handoff payload for object
store artifacts. The service does not expose write endpoints or generic raw
table-dump routes.
