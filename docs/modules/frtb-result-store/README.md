# frtb-result-store

`frtb-result-store` persists FRTB calculation evidence for analytics and
reporting. It is a storage and query package, not a capital calculation package.

See [FIRST_PASS_DESIGN.md](FIRST_PASS_DESIGN.md) for the target result-store
design covering business hierarchy, deterministic run identity, artifact
writing, marts, FastAPI serving, lifecycle events, exports, and S3 Parquet
support.

See [DETAILED_DESIGN.md](DETAILED_DESIGN.md) for implementation-level storage,
schema, API, and backend details. See [STORAGE_CONTRACT.md](STORAGE_CONTRACT.md)
for manifest-gated write semantics, rollback behavior, orphan handling, and
evidence boundaries. See [BACKEND_ACCEPTANCE_CRITERIA.md](BACKEND_ACCEPTANCE_CRITERIA.md)
before enabling a non-test object-store backend. See [ISSUE_BREAKDOWN.md](ISSUE_BREAKDOWN.md)
for the GitHub issue plan derived from that design.

The first implementation uses DuckDB over local Parquet files. A stored run is
append-only and contains:

- `CalculationRun` identity and lineage metadata;
- capital graph `CapitalNode` and `CapitalEdge` records;
- scalar `CapitalMeasure` rows for capital and intermediate values;
- `ArtifactRef` rows for drillthrough tables and vectors;
- `CapitalAttributionRecord` rows for Euler, residual, and unsupported
  attribution methods;
- `LineageRef` rows tying stored results to inputs, policies, and hashes.

The model is intentionally FRTB-specific: nodes carry component, desk,
portfolio, risk-class, bucket, issuer, counterparty, calculation-branch, and
regulatory-rule dimensions. Large numerical vectors are referenced by URI
rather than embedded in dashboard query rows.
