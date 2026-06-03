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

Example:

```python
from pathlib import Path

from frtb_result_store import DuckDbParquetResultStore, ResultBundle

store = DuckDbParquetResultStore(Path("dist/result-store"))
store.write_bundle(ResultBundle(...))
runs = store.list_runs()
```

The API is FRTB-specific. Consumers should query capital trees, node measures,
artifact references, lineage, and attribution records rather than treating the
store as a generic table dump.

The optional FastAPI service is available through the `api` extra. It exposes
read-only domain endpoints for runs, run groups, capital trees, artifacts,
attribution, lineage, events, movements, and regime comparison. It does not
share the writer catalog or expose generic raw table dumps.
