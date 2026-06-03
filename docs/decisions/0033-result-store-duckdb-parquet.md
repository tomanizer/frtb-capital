# 33. Result-store storage and observability dependencies

Date: 2026-06-03

## Status

Accepted

## Context

The suite can now produce meaningful component-level and orchestration-level
FRTB outputs. Analysts and reporting systems need a result store that can serve
top-of-house capital, desk drilldown, component drilldown, large IMA vectors,
SBM/DRC/CVA detail, regime comparisons, lineage, and capital attribution.

The protected calculation kernels must remain free of storage-engine
dependencies. ADR 0011 requires an ADR before new runtime dependencies enter
the suite. ADR 0023 allows PyArrow at tabular handoff and IO boundaries, and
ADR 0012 requires attribution readiness for capital aggregation branches.

The result store needs runtime libraries that are not part of the capital
kernel dependency set:

- DuckDB as an embedded query/catalog engine over a Parquet layout.
- PyArrow for artifact schemas, chunked Parquet IO, and mart generation.
- OpenTelemetry API as the optional runtime observability integration point for
  traces and metrics.

Two enforcement mechanisms must be addressed with the dependency decision:

- the root import-linter configuration must enforce that result-store imports
  shared primitives only and that capital/orchestration packages do not import
  the result store;
- the kernel import-boundary checker must treat `frtb-result-store` as an
  approved IO/serving package rather than a capital kernel package.

## Decision

Add `frtb-result-store` as a new package in the existing monorepo.

The package owns storage and query contracts for completed FRTB calculation
evidence. It does not implement capital formulae and it does not become a
dependency of capital packages.

The first backend is local DuckDB over Parquet:

```text
result-store-root/
  catalog.duckdb
  manifests/
  parquet/
    runs/
    capital_nodes/
    capital_edges/
    capital_measures/
    artifact_refs/
    lineage_refs/
    capital_attributions/
```

Stored runs are append-only by `run_id`. Corrections, recalculations, regime
variants, and restatements must create new runs. Re-committing an already
manifested `run_id` fails closed; supersession is represented by lifecycle
events, not overwrite.

Deterministic IDs use the full `frtb_common.hashing.stable_json_hash` digest as
the storage key. Short prefixes may be displayed to users but are not accepted
as storage identifiers. If an implementation exposes aliases, it must verify
that an alias maps to exactly one full identity payload before returning data.

The central model is a capital result graph:

- `CalculationRun` stores as-of date, regime, base currency, input snapshot,
  engine version, code version, policy id, scope, creation time, and metadata.
- `CapitalNode` and `CapitalEdge` store FRTB-specific drilldown structure.
- `CapitalMeasure` stores scalar capital and intermediate values.
- `ArtifactRef` points to large Parquet/Arrow drillthrough data such as IMA P&L
  vectors, ES tail observations, SBM sensitivities, DRC JTD tables, CVA
  exposures, attribution vectors, and movement explanations.
- `CapitalAttributionRecord` stores Euler, residual, and unsupported
  attribution rows compatible with `frtb_common.CapitalContribution`.
- `LineageRef` ties stored results to input snapshots, source rows, policy
  objects, and hashes.

S3 Parquet and DuckLake are recorded as backend modes but reserved for later
implementation. Artifact URIs may already point to object storage. The commit
protocol is manifest-led for both local and future object-store backends: base
tables, artifacts, and marts are staged first; the run manifest is the commit
marker; readers ignore any staged or orphaned object that lacks a committed
manifest.

The result store is not part of the existing orchestration/capital layers
contract. Orchestration is allowed to import capital components; the result
store is not. The boundary is therefore expressed through explicit forbidden
import-linter contracts:

- `frtb_result_store` must not import `frtb_orchestration` or any capital
  component package;
- `frtb_common`, `frtb_orchestration`, and all capital component packages must
  not import `frtb_result_store`.

Callers project component or orchestration outputs into neutral result-store
DTOs in a future adapter/application layer that is outside this ADR.

Dependency posture:

- `pyarrow` is allowed in this package for Parquet/Arrow IO and artifact
  schema validation under ADR 0023; it remains outside calculation kernels. The
  kernel import-boundary checker skips `packages/frtb-result-store/src` because
  the package is IO/serving infrastructure, not a kernel package.
- DuckDB is an optional backend dependency. Importing core domain contracts from
  `frtb_result_store` must not require DuckDB.
- OpenTelemetry API is an optional instrumentation dependency. The package may
  instrument traces and metrics through the lightweight `opentelemetry-api`,
  but SDK, exporter, collector, sampling, and backend configuration belong to
  applications and deployments. Standard logging may carry trace context where
  available.
- FastAPI remains an optional serving dependency.

Not approved by this ADR:

- SQLAlchemy for the DuckDB/Parquet backend;
- OpenTelemetry SDKs, exporters, collectors, samplers, or backend
  configuration inside the library;
- DuckLake;
- pandas or polars in the result-store runtime path.

The DuckDB catalog is derived and disposable. Long-lived read services should
open their own read-only or in-memory DuckDB connection over committed Parquet
and manifests rather than sharing a mutable writer catalog across processes.

## Consequences

- The result store stays close to evolving public result contracts while those
  contracts mature.
- DuckDB and PyArrow are introduced only in the result-store package and remain
  outside capital kernels; DuckDB is required only for the DuckDB backend and
  read helpers.
- OpenTelemetry API is approved only as optional instrumentation; deployments
  choose SDK/exporter/collector configuration.
- The result-store package boundary is machine-enforced in both directions,
  protecting the guarantee that storage does not enter capital kernels and the
  store does not depend on capital components.
- The kernel-boundary checker gains a package-level exemption for
  `frtb-result-store`; future capital kernels must not be placed in that
  package.
- FRTB analysis APIs can query pre-shaped runs, graph nodes, measures, artifact
  references, lineage, and attribution records instead of scanning raw vectors
  for every dashboard request.
- The first backend is single-writer/local. Multi-writer table management,
  object-store writes, snapshot isolation, retention policy, and DuckLake
  catalog management remain follow-on work. The manifest-led commit protocol is
  still specified now so S3 mode can reuse the same reader contract.
- Outputs stored by this package are calculation evidence produced by the
  suite; this decision does not reclassify them as final regulatory capital.

## References

- ADR 0012: Capital impact attribution.
- ADR 0011: Core runtime dependency policy.
- ADR 0023: Arrow tabular handoff boundary.
- ADR 0032: Analytical Euler decomposition framework.
