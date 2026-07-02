# frtb-result-store public API

| Contract | Purpose |
| --- | --- |
| `PACKAGE_METADATA`, `__version__` | Workspace discovery and maturity reporting. |
| `CalculationRun` | Immutable FRTB run identity. |
| `CapitalNode`, `CapitalEdge` | FRTB capital result graph. |
| `CapitalMeasure` | Scalar capital and intermediate measures. |
| `ArtifactRef` | URI-backed large drillthrough artifacts. |
| `ARTIFACT_SCHEMA_REGISTRY`, `artifact_schema_for` | Strict schemas for staged Parquet artifacts. |
| `CapitalAttributionRecord` | Attribution rows for Euler, residual, and unsupported methods. |
| `RiskFactorMetadataSnapshot`, `RiskFactorMetadataRecord`, `RiskFactorSourceMapping` | Fixture-backed canonical risk-factor metadata read model. |
| `LineageRef` | Result-to-source lineage references. |
| `ResultBundle` | Append-only payload written for one run. |
| `DuckDbParquetResultStore` | Local Parquet writer and DuckDB query facade. |
| `create_result_store_app` | Optional read-only FastAPI app factory. |
| `frtb-result-store` | Optional admin CLI for inspection, catalog refresh, validation, and export. |

Example:

```python
from pathlib import Path

from frtb_result_store import DuckDbParquetResultStore, ResultBundle

store = DuckDbParquetResultStore(Path("dist/result-store"))
store.write_bundle(ResultBundle(...))
runs = store.list_runs()
```

The API is FRTB-specific. Consumers should query capital trees, node measures,
artifact references, lineage, attribution records, and attribution explain
projections rather than treating the store as a generic table dump.
Risk-factor metadata is exposed through domain query methods such as
`risk_factor_snapshots`, `risk_factor_metadata`,
`get_risk_factor_metadata`, `risk_factor_metadata_by_classification`, and
`risk_factor_source_mappings`; these methods serve fixture-backed viewer read
models and do not provide production reference-data management or calculation
logic.
Risk-factor drilldown is exposed through bounded UI/API contracts:
`list_risk_factors`, `get_risk_factor`, `risk_factor_lineage`,
`risk_factor_capital`, and `risk_factor_source_rows`. These methods return
explicit `available` or `no_data` states. Capital drilldown aggregates only
persisted attribution rows that identify the selected risk factor; missing
RFET, UPL, CRIF, stress-vector, or contribution evidence is not reconstructed.
Future OLAP-backed implementations should preserve these aggregate/detail
payload shapes and pagination limits while replacing only the query engine.

Registered artifact schemas include the original `ima.pnl_vector.v1` plus
common metadata/evidence schemas for `common.time_series.v1`,
`common.shock_definition.v1`, `common.scenario_vector_metadata.v1`, and
`common.surface_grid.v1`. These schemas support RFET timelines, PLA/backtesting
vectors, stress/scenario metadata, SBM curvature shocks, and surface-grid
inspection without requiring capital kernels or frontend code to own canonical
artifact storage.

Base-table row assembly is split across internal IO stages:
`frtb_result_store.store_bundle_rows` assembles one `ResultBundle` into table
row groups, and `frtb_result_store.store_status_rows` owns lifecycle status row
serialization. The older `frtb_result_store.store_row_io` module remains an
internal compatibility path for existing row helper imports.
Risk-factor metadata row serialization lives in
`frtb_result_store.risk_factor_metadata_rows` with compatibility aliases in
`store_row_io`.

Reporting mart generation is also stage-split internally: component-breakdown
rows live in `frtb_result_store.mart_component_breakdown_rows`, movement-summary
mart rows live in `frtb_result_store.mart_movement_rows`, and
`frtb_result_store.marts` remains the public mart projection facade.

`DuckDbParquetResultStore.refresh_catalog()` rebuilds `catalog.duckdb` as
derived state over committed Parquet. `read_only_connection()` opens that
derived catalog with DuckDB read-only mode where supported; callers must close
the returned connection. `inspect()`, `validate_store()`, and `export_run(...)`
support operator workflows without making the catalog durable evidence.

The admin CLI emits JSON:

```text
frtb-result-store inspect <root>
frtb-result-store list-runs <root>
frtb-result-store refresh-catalog <root>
frtb-result-store export-run <root> <run-id> <output-path>
frtb-result-store validate-store <root>
```

Single-run export writes `run_manifest.json`, `parquet/base/`, `parquet/marts/`,
available artifact Parquet under `parquet/artifacts/`, and `checksums.json`.
`catalog.duckdb` is excluded because it is rebuildable. Import and lifecycle
workflow management are out of scope for the CLI.

The optional FastAPI service is available through the `api` extra. It exposes
read-only domain endpoints for runs, run groups, capital trees, artifacts,
attribution, top contributor attribution, residual attribution, unsupported
attribution, risk-factor metadata/drilldown, lineage, events, movements, and
regime comparison. Risk-factor routes include
`GET /runs/{run_id}/risk-factors`,
`GET /runs/{run_id}/risk-factors/{risk_factor_id}`,
`GET /runs/{run_id}/risk-factors/{risk_factor_id}/lineage`,
`GET /runs/{run_id}/risk-factors/{risk_factor_id}/capital`, and
`GET /runs/{run_id}/risk-factors/{risk_factor_id}/source-rows`. Artifact
drillthrough is served through deterministic paged Parquet reads with optional
column selection and simple equality filters, plus local Parquet download or
S3 URI handoff. The service does not share the writer catalog or expose generic
raw table dumps.
`create_result_store_app(..., cors_allow_origins=(...))` can opt in to local
browser access for the static FRTB Navigator viewer; CORS is disabled by
default.

Metadata-backed artifact endpoints wrap the same deterministic paging contract
with domain names for dashboards and future OLAP adapters:

```text
GET /runs/{run_id}/time-series
GET /runs/{run_id}/time-series/{time_series_id}/points
GET /runs/{run_id}/shocks
GET /runs/{run_id}/shocks/{shock_id}
GET /runs/{run_id}/scenario-vectors
GET /runs/{run_id}/scenario-vectors/{scenario_set_id}/{scenario_vector_id}/metadata
GET /runs/{run_id}/surfaces
GET /runs/{run_id}/surfaces/{surface_id}/slice
```

These endpoints return persisted artifact rows and lineage fields only. They do
not infer regulatory classifications, generate shocks, interpolate surfaces, or
materialize unbounded raw frames into the client.
The list endpoints return both full artifact refs and a compact `catalog` array
with `artifact_id`, `component`, `artifact_status`, `status_reason`,
`navigator_role`, `row_count`, and semantic `partition_values`. Dashboards
should use the catalog for selectors and status badges, then call the paged
detail endpoints for row data. List payloads also include `status_counts`
covering `AVAILABLE`, `NO_DATA`, and `UNSUPPORTED` refs for the metadata family.
The dashboard-facing selection, no-data, reconciliation, and cache/cancellation
contract is documented in
[`FRTB_NAVIGATOR_METADATA_CONTRACT.md`](FRTB_NAVIGATOR_METADATA_CONTRACT.md).
The developer-facing overview of schema fields, availability states, fixture
examples, and implementation limits is documented in
[`ARTIFACT_METADATA.md`](ARTIFACT_METADATA.md).

The FRTB Navigator fixture includes concrete examples for each metadata
family: an RFET observation time series, SBM curvature up/down shock
definitions, an IMA RTPL scenario vector, and a two-axis USD swaption volatility
surface. It also includes explicit no-data/unsupported refs for absent UPL,
RFET/stress-period extensions, and CRIF drillthrough, so UI agents can exercise
both available and unavailable states through the same artifact contract.
Relevant capital nodes link to these metadata artifacts through the normal
`/runs/{run_id}/nodes/{node_id}/lineage` endpoint; clients do not need a
separate provenance mechanism for timelines, shocks, scenario vectors, or
surfaces.
Unavailable metadata refs also carry semantic `partition_values` where a stable
identifier exists. For example, a missing UPL vector can be requested through
`/runs/{run_id}/time-series/{time_series_id}/points` and returns
`mode=artifact_unavailable` rather than a 404 or fabricated empty Parquet page.

Attribution projection helpers and endpoints are storage-only:
`top_contributors`, `residual_attribution_records`, and
`unsupported_attribution_records` expose fields already present on
`CapitalAttributionRecord`, including `contribution`, `residual`, `method`,
`source_id`, `source_level`, `target_id`, and `unsupported_reason`. They do not
implement capital or attribution formulae. Internal attribution projection mart
row assembly lives in `frtb_result_store.mart_attribution_rows`;
`frtb_result_store.marts` remains the public reporting-mart facade and
compatibility import path.

Internal capital-tree mart row assembly lives in
`frtb_result_store.mart_capital_tree_rows`; `frtb_result_store.marts` remains
the public reporting-mart facade and compatibility import path.
