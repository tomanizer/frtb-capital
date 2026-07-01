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
    risk_factor_metadata_snapshots/
    risk_factor_metadata/
    risk_factor_source_mappings/
```

Each table receives one Parquet file per immutable `run_id`. A run becomes
visible only when its `run_manifest.json` exists; readers ignore staged or
orphaned Parquet files without a manifest. DuckDB queries run over committed
Parquet files through independent connections. `catalog.duckdb` is derived
convenience state and can be rebuilt.

S3 Parquet mode uses the same logical layout under an `s3://` root and the
same manifest-as-commit-marker reader contract as local mode. Local integration
tests and development use an explicit mock root, so readers and writers
exercise the S3 layout without hard-coded credentials. DuckDB object-store
access is configured through extension and setting hooks such as `httpfs`.
DuckLake remains a reserved backend mode.

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

## Time-series, shock, scenario, and surface artifacts

The result store owns canonical persisted metadata for analytical artifacts that
are too large, too evidence-heavy, or too reference-data-like to live inside
scalar capital rows. Registered artifact schemas now cover:

- `common.time_series.v1` for observed or calculated timelines such as RFET
  real-price observations, PLA/backtesting vectors, or UPL vectors when those
  fixtures exist;
- `common.shock_definition.v1` for persisted shock definitions, including
  direction, type, magnitude, unit, source row, mapping version, and optional
  regulatory rule id;
- `common.scenario_vector_metadata.v1` for scenario-set and scenario-vector
  metadata that links dense IMA arrays to scenario ids, dates, labels, and
  source rows;
- `common.surface_grid.v1` for volatility or surface-like grids with explicit
  axis names, axis values, surface point ids, risk-factor links, and source row
  provenance.

These schemas are read-model and evidence contracts. They are not pricing,
interpolation, scenario-generation, or capital-calculation engines. Dense
numeric payloads can remain behind artifact ids and storage adapters; dashboards
and APIs should page or slice artifact rows instead of loading entire raw frames.
Two-dimensional surface points should use the package-neutral
`frtb_common.SurfacePointCoordinates` primitive at component/orchestration
boundaries and `common.surface_grid.v1` rows in the result-store read model.
The concrete Capital Navigator consumption contract for these artifact families
is in
[`CAPITAL_NAVIGATOR_METADATA_CONTRACT.md`](CAPITAL_NAVIGATOR_METADATA_CONTRACT.md).

## Boundary rules

Capital packages emit result objects and audit records. They must not import
DuckDB, Parquet writers, or `frtb-result-store`. The result-store package may
depend on `frtb-common` and public suite contracts, but this first slice keeps
runtime dependencies to `frtb-common`, DuckDB, and PyArrow.

For time-series, shock, scenario-vector, and surface metadata, component kernels
consume validated arrays or scalar inputs plus stable ids/provenance. They must
not fetch artifacts, perform market-data lookup, infer missing UPL or stress
vectors, or generate shock/surface definitions from stored metadata.
