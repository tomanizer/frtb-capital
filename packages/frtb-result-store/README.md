# frtb-result-store

DuckDB/Parquet result-store package for FRTB capital evidence.

The package persists immutable calculation runs, capital result graph nodes,
scalar measures, lineage references, attribution records, and large-artifact
references. It is storage and serving infrastructure only; capital formulae
remain in the IMA, SBM, DRC, RRAO, CVA, and orchestration packages.

Attribution storage behavior and limitations are documented in
[`ATTRIBUTION.md`](ATTRIBUTION.md).

## End-to-end example

Run the package demo to see a completed synthetic suite result handed to the
store as a `ResultBundle`, committed through `DuckDbParquetResultStore`, and
queried back for total capital, component breakdown, attribution records, and
lineage:

```bash
uv run python packages/frtb-result-store/examples/run_demo.py
```

The demo uses only public `frtb_common` and `frtb_result_store` contracts. It
writes to a temporary local Parquet store and removes it after the run.

Current runtime support is deliberately narrow:

- append-only `CalculationRun` bundles;
- FRTB-specific `CapitalNode` and `CapitalEdge` graph drilldown;
- scalar `CapitalMeasure` rows for capital and intermediate amounts;
- `ArtifactRef` rows for IMA P&L vectors, ES tail observations, SBM
  sensitivities, DRC JTD tables, CVA exposures, attribution vectors, and
  movement explanations;
- `CapitalAttributionRecord` rows compatible with
  `frtb_common.CapitalContribution`;
- fixture-backed organisational hierarchy read-model contracts for
  top-of-house, legal entity, business division, business line, desk, Volcker
  desk, and book rollups;
- manifest-gated local and S3-layout Parquet files queried through independent
  DuckDB connections;
- best-effort read-only SQL helper and admin CLI for inspection, disposable
  catalog refresh, validation, and one-way run export;
- optional read-only FastAPI service via `frtb-result-store[api]`.

S3 Parquet mode accepts an `s3://bucket[/prefix]` root and keeps the same
logical `parquet/`, `artifacts/`, and `manifests/` layout as local mode. Runs
are still discovered only from committed run manifests, so staged or orphaned
objects remain invisible to readers. Local integration tests and development
can use `ResultStoreConfig(..., backend=StorageBackend.S3_PARQUET,
s3_mock_root=...)`; artifact refs and manifest paths retain the logical
`s3://` URI while Parquet bytes are written to the mock root. DuckDB `httpfs`
and S3 credentials are configured only through `duckdb_extensions`,
`duckdb_install_extensions`, and `duckdb_settings`; the package does not
hard-code credentials.

DuckLake remains an explicit reserved backend mode.

`catalog.duckdb` is derived convenience state over committed Parquet files. It
can be deleted and rebuilt with `DuckDbParquetResultStore.refresh_catalog()` or
`frtb-result-store refresh-catalog <root>`; it is not durable evidence and is
excluded from exports. `DuckDbParquetResultStore.read_only_connection()` opens
that derived catalog with DuckDB read-only mode after refreshing it when needed.

The admin CLI emits JSON for each command:

```text
frtb-result-store inspect <root>
frtb-result-store list-runs <root>
frtb-result-store refresh-catalog <root>
frtb-result-store export-run <root> <run-id> <output-path>
frtb-result-store validate-store <root>
```

`export-run` writes a one-way evidence bundle containing `run_manifest.json`,
`parquet/base/`, `parquet/marts/`, copied local or mock-S3 artifact Parquet under
`parquet/artifacts/`, and `checksums.json`. Import, approval, and lifecycle
workflow commands are intentionally not provided.

First-pass persisted marts are generated for `capital_summary`, `capital_tree`,
`top_contributors`, `residual_attribution`, `unsupported_attribution`,
`movement_summary`, `regime_comparison`, `component_breakdown`,
`ima_desk_dashboard`, `sbm_bucket_ladder`, `drc_issuer_contributors`,
`cva_counterparty_contributors`, and `rrao_exposure_summary`. The package test
`test_representative_dashboard_query_latency_fixture` records representative
latency envelopes for local synthetic data: summary, capital tree, and
top-contributor mart reads are expected below 250 ms, while artifact first-page
drillthrough is expected below 1000 ms. These are local first-pass envelopes,
not production SLOs; large object-store artifacts, cold DuckDB extension loads,
remote storage latency, and analyst concurrency are outside the benchmark
fixture.

The FastAPI service is created with `create_result_store_app(...)`. It exposes
FRTB-specific read endpoints for runs, run groups, capital trees, measures,
artifacts, attribution, attribution explain projections, lineage, events,
movements, and regime comparison. It also supports artifact drillthrough with
deterministic Parquet-backed pages:
`GET /runs/{run_id}/artifacts/{artifact_id}/page` accepts `limit`, `offset`,
repeated or comma-separated `columns`, and repeated `filter=column=value`
parameters. `GET /runs/{run_id}/artifacts/{artifact_id}/download` serves local
Parquet artifacts directly and returns an S3 URI handoff payload for object
store artifacts. The service does not expose write endpoints or generic raw
table-dump routes.

## Organisational Hierarchy Fixtures

`frtb_result_store.org_hierarchy` provides the public read-model contracts used
to roll mapped capital rows up through an enterprise hierarchy. The supported
levels are `TOH`, `LEGAL_ENTITY`, `BUSINESS_DIVISION`, `BUSINESS_LINE`, `DESK`,
`VOLCKER_DESK`, and `BOOK`. `TOH` is the top-of-house group aggregate across
legal entities. `BOOK` is the normal leaf, while desk-level source rows remain
valid when book data is unavailable.

The committed synthetic fixture returned by `sample_org_hierarchy()` includes
`GLOBAL_GROUP`, `US_BANK_NA`, `UK_BANK_PLC`, `MARKETS`, `TREASURY`, `FICC`,
`FX`, `EQUITIES`, `USD_RATES_VOLCKER`, `G10_FX_SPOT`, `US_CASH_EQUITIES`,
`USD_SWAP_BOOK_01`, `EURUSD_SPOT_BOOK`, and `US_EQ_BOOK_01`. The fixture also
includes a UK treasury desk row and explicit 2025/2026 effective-dated hierarchy
versions so historical run dates resolve to one version.

`sample_org_capital_rows()` returns synthetic component rows with
`OrgSliceKeys`. At least one row is mapped at book grain and at least one row is
mapped only at desk grain. `validate_org_hierarchy(...)` checks the single-root
rule, duplicate nodes, cycles, missing parents, effective dates, row key
existence, run-date version resolution, and whether supplied book/desk/legal
entity keys are on the same ancestor path.

`aggregate_by_org_hierarchy(...)` returns deterministic `OrgAggregateRow`
objects with URL-safe row IDs, parent IDs, group paths, capital totals, source
row counts, and component breakdowns. `source_rows_for_org_aggregate(...)`
traces an aggregate row back to the source rows under that branch; selecting
`GLOBAL_GROUP > US_BANK_NA > MARKETS > FICC > USD_RATES_VOLCKER` returns only
the source rows under that Volcker desk, while selecting `GLOBAL_GROUP` returns
all source rows for the hierarchy version.

`list_org_hierarchy(...)`, `org_node_children(...)`, `aggregate_org_node(...)`,
and `source_rows_for_org_node(...)` provide the narrower Navigator query
contract. They resolve one effective hierarchy version for a run date, keep
aggregate and source-row lookups separate, page source rows with `limit` and
`offset`, and return explicit `OK`, `NO_DATA`, or `UNSUPPORTED` statuses rather
than asking the dashboard to infer missing fixture datasets. The FastAPI app
exposes the same read-only contract under
`/runs/{run_id}/org-hierarchy/...` for deterministic synthetic runs.

This is fixture/read-model infrastructure, not production master data,
entitlements, SSO, or a general OLAP engine. Component packages preserve
stable identifiers and audit records, but they must not traverse the enterprise
hierarchy; hierarchy traversal belongs in the result store and later dashboard
API adapters.
