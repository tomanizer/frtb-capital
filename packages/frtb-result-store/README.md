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
- manifest-gated local Parquet files queried through independent DuckDB
  connections.

S3 Parquet and DuckLake are explicit backend modes but reserved for later
implementation. Artifact URIs may already point at object storage, while this
first backend owns local result-store Parquet files.
