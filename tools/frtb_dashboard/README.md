# FRTB Capital Navigator tools

This directory contains read-only Capital Navigator tooling for synthetic FRTB
analysis and result-store metadata inspection. The tools do not calculate
capital, fetch raw object-store files, generate shocks, interpolate surfaces, or
synthesize missing rows.

## Metadata viewer

The dependency-free static metadata shell consumes the read-only
`frtb-result-store` FastAPI metadata endpoints for one committed run.

Serve this directory with any static file server, then point the UI at a running
result-store API.

```bash
python3 -m http.server 5177 --directory tools/frtb_dashboard
```

Default settings:

- API base: `http://127.0.0.1:8000`
- run id: `frtb/capital-navigator/2026-06-03/us-npr`

If the static viewer and API run on different local origins, create the FastAPI
app with an explicit CORS allow-list, for example
`create_result_store_app(store, cors_allow_origins=("http://127.0.0.1:5177",))`.

The metadata shell expects the metadata contract documented in
`docs/modules/frtb-result-store/CAPITAL_NAVIGATOR_METADATA_CONTRACT.md`.

It inspects:

- time-series catalogs and paged points;
- shock-definition catalogs and paged rows;
- scenario-vector metadata catalogs and paged rows;
- surface catalogs and filtered surface slices;
- canonical risk-factor metadata, lineage, stored capital contribution state,
  and bounded source-row mappings from the result-store risk-factor APIs;
- artifact availability states: `AVAILABLE`, `NO_DATA`, and `UNSUPPORTED`;
- artifact-row lineage/provenance fields for inspection.

For the result-store schema and endpoint guides, see
`docs/modules/frtb-result-store/PUBLIC_API.md` and
`docs/modules/frtb-result-store/ARTIFACT_METADATA.md`.

## Capital Navigator v2 dashboard

The v2 dashboard is a high-density, read-only viewer for synthetic FRTB capital
run results across IMA, SA, and CVA. It uses a fixed four-zone layout: command
ribbon, context bar, aggregate blotter, and audit inspector.

See [`docs/tools/frtb-dashboard/DESIGN.md`](../../docs/tools/frtb-dashboard/DESIGN.md)
for the design contract and roadmap.

### Quick start

```bash
# API, serving the built frontend when dist/ exists
uv run --with uvicorn python tools/frtb_dashboard/run.py --port 8766

# Frontend dev server
cd tools/frtb_dashboard/frontend && npm install && npm run dev
```

Open http://localhost:5174 in development or http://127.0.0.1:8766 after a
production frontend build.

### v2 capabilities

- Backend-computed top-of-house binding capital: `max(IMA, 0.725 * SA)`.
  The multiplier is a non-regulatory demo value aligned to the current
  `frtb-orchestration` scope-view default; production views should use the
  resolved floor multiplier from persisted run payloads.
- Selectable hierarchy rail for top-of-house, legal entity, division, business
  line, desk, Volcker desk, and book scopes.
- SA blotter with SBM scenario columns, DRC bucket rows, and RRAO evidence rows.
- IMA blotter with IMCC, SES, PLA, backtesting, multiplier, and attribution.
- CVA no-data state when the selected run has no CVA payload.
- Inspector linked to the selected aggregate row, showing attribution, source
  provenance, scenario/backtesting extras, and data-honesty diagnostics.
- Abortable frontend requests and small in-memory caches for run, blotter, and
  inspector payloads keyed by run, framework, scenario, hierarchy node, and row.

## Boundaries

The current v2 dashboard is dependency-light and fixture-backed. The API
contract is shaped for a later OLAP implementation over DuckDB/ClickHouse/Impala
and for AG Grid Enterprise SSRM once the licensed dependency and production data
source are available.

The static metadata shell intentionally does not implement the production OLAP
backend, AG Grid Enterprise, entitlements, market-data sourcing, shock
generation, surface interpolation, RFET vendor remediation, regulatory
risk-factor classification, or capital calculation. Those remain outside this
tool directory and are documented as boundaries in ADRs 0049-0052 and
`docs/RISK_FACTOR_METADATA_OWNERSHIP.md`.
