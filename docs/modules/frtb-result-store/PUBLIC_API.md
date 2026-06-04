# frtb-result-store public API

| Contract | Purpose |
| --- | --- |
| `PACKAGE_METADATA`, `__version__` | Workspace discovery and maturity reporting. |
| `CalculationRun` | Immutable FRTB run identity. |
| `CapitalNode`, `CapitalEdge` | FRTB capital result graph. |
| `CapitalMeasure` | Scalar capital and intermediate measures. |
| `ArtifactRef` | URI-backed large drillthrough artifacts. |
| `CapitalAttributionRecord` | Attribution rows for Euler, residual, and unsupported methods. |
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
attribution, lineage, events, movements, and regime comparison. Artifact
drillthrough is served through deterministic paged Parquet reads with optional
column selection and simple equality filters, plus local Parquet download or
S3 URI handoff. The service does not share the writer catalog or expose generic
raw table dumps.

Attribution projection helpers and endpoints are storage-only:
`top_contributors`, `residual_attribution_records`, and
`unsupported_attribution_records` expose fields already present on
`CapitalAttributionRecord`, including `contribution`, `residual`, `method`,
`source_id`, `source_level`, `target_id`, and `unsupported_reason`. They do not
implement capital or attribution formulae.
