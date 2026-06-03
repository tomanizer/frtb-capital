# CLAUDE.md — frtb-result-store

Review `frtb-result-store` as storage and serving infrastructure only.

Reject capital formulae, sibling capital-package imports in storage paths, or
mutable run semantics. Runs are append-only; corrections require a new `run_id`.

Keep DuckDB, Parquet, and Arrow inside IO, artifact, catalog, and API modules.
Capital packages and orchestration must not import `frtb-result-store` unless a
future ADR changes the boundary.

`catalog.duckdb` is derived convenience state over committed Parquet manifests,
not durable evidence. Review changes against
[`docs/decisions/0034-result-store-duckdb-parquet.md`](../../docs/decisions/0034-result-store-duckdb-parquet.md)
and [`docs/modules/frtb-result-store/STORAGE_CONTRACT.md`](../../docs/modules/frtb-result-store/STORAGE_CONTRACT.md).