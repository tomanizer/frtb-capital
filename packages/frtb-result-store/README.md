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

The FastAPI service is created with `create_result_store_app(...)`. It exposes
FRTB-specific read endpoints for runs, run groups, capital trees, measures,
artifacts, attribution, lineage, events, movements, and regime comparison. It
does not expose write endpoints or generic raw table-dump routes.
