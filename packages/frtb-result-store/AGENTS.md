# AGENTS.md — frtb-result-store

Follow the suite-level portable worktree policy in
[`../../AGENTS.md`](../../AGENTS.md) and
[`../../docs/AGENT_WORKTREE_POLICY.md`](../../docs/AGENT_WORKTREE_POLICY.md)
before editing this package.

`frtb-result-store` owns storage and query contracts for FRTB calculation
evidence.

## Current status

The package has a first local DuckDB/Parquet backend:

- append-only run bundles;
- capital result graph nodes and edges;
- scalar capital and intermediate measures;
- large-artifact references for vector and drillthrough data;
- lineage and attribution records.

## Rules

- Do not implement capital formulae in this package.
- Do not import private modules from capital packages.
- Keep DuckDB, Parquet, and Arrow dependencies inside result-store IO and
  artifact handling modules.
- Capital packages must not import `frtb-result-store`.
- Own canonical persisted metadata and read APIs for time series, shocks,
  scenario vectors, and surfaces. Store resolved artifact IDs, partition keys,
  mapping versions, lineage, and explicit no-data/unsupported states; do not
  infer component regulatory semantics or fabricate missing artifact payloads.
- Preserve append-only run semantics; corrections require a new `run_id`.
- Keep artifact references URI-based so local and object-storage drillthrough
  can share the same domain model.
