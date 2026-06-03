# frtb-result-store architecture and data design

## Purpose

`frtb-result-store` is the suite-level evidence store for completed FRTB
calculation results. It stores enough structure to serve dashboards, report
drilldowns, regime comparisons, capital movement analysis, lineage inspection,
and attribution without coupling capital kernels to storage infrastructure.

## First backend

The first backend is local DuckDB over Parquet:

```text
result-store-root/
  catalog.duckdb
  manifests/
    <run-id>/run_manifest.json
  parquet/
    runs/
    capital_nodes/
    capital_edges/
    capital_measures/
    artifact_refs/
    lineage_refs/
    capital_attributions/
```

Each table receives one Parquet file per immutable `run_id`. DuckDB views are
created over the Parquet table directories for analyst and API query paths.

S3 Parquet and DuckLake are reserved backend modes. The domain model already
stores artifact URIs, so IMA P&L vectors, ES tail observations, SBM
sensitivities, DRC JTD tables, CVA exposures, and attribution vectors can live
outside the scalar serving rows.

## Data model

The core shape is a capital result graph:

- `CalculationRun` identifies the date, regime, input snapshot, engine version,
  code version, policy id, base currency, and calculation scope.
- `CapitalNode` represents FRTB-specific drilldown points such as total capital,
  IMA desk, SA stack, SBM risk class, DRC issuer, RRAO residual-risk type, or
  CVA counterparty.
- `CapitalEdge` records aggregation and drilldown relationships.
- `CapitalMeasure` stores scalar capital and intermediate measures.
- `ArtifactRef` points to large drillthrough data.
- `CapitalAttributionRecord` stores Euler, residual, or unsupported attribution
  rows compatible with `frtb_common.CapitalContribution`.
- `LineageRef` ties stored results to input rows, snapshots, policy objects, or
  source hashes.

## Boundary rules

Capital packages emit result objects and audit records. They must not import
DuckDB, Parquet writers, or `frtb-result-store`. The result-store package may
depend on `frtb-common` and public suite contracts, but this first slice keeps
runtime dependencies to `frtb-common`, DuckDB, and PyArrow.
