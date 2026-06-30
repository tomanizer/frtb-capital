# FRTB Capital Dashboard

Interactive dashboard for exploring FRTB capital run results across **IMA** and the
**Standardised Approach** (SBM + DRC + RRAO), with attribution drill-down.

See [`docs/tools/frtb-dashboard/DESIGN.md`](../../docs/tools/frtb-dashboard/DESIGN.md) for
requirements, information architecture, and phased delivery.

## Quick start

```bash
# API (serves built frontend when dist/ exists)
uv run --with uvicorn python tools/frtb_dashboard/run.py --port 8766

# Frontend dev server
cd tools/frtb_dashboard/frontend && npm install && npm run dev
```

Open http://localhost:5174 (dev) or http://127.0.0.1:8766 (production build).

## Tests

```bash
# Backend (API + demo run builders)
uv run pytest tests/test_frtb_dashboard.py -q

# Frontend (Vitest: render smoke + formatting/reconciliation units)
cd tools/frtb_dashboard/frontend && npm test
```

## Configuration

- `FRTB_DASHBOARD_CORS_ORIGINS` — comma-separated allowed origins. Defaults to the
  local Vite dev server (`http://127.0.0.1:5174`, `http://localhost:5174`); set it
  explicitly for any shared deployment instead of using a wildcard.

## MVP (P0) capabilities

A **capital-workbench** layout (capital tree is the source of truth; dashboard
visuals are a companion rail), following the vendor-frontend review in
[`docs/modules/vendor-frtb-frontends.md`](../../docs/modules/vendor-frtb-frontends.md).

- Synthetic **demo-suite-001** run built from public package fixtures and demos
- Run picker (catalogue-backed) and breadcrumb navigation
- Capital tree with columns: capital, **% of parent**, provisional markers
- **Deterministic drill-down workbench** — every node shows the same tab spine
  (Summary first, Attribution + Diagnostics always present and last; IMA adds
  IMCC/ES, SES & NMRF, PLA, Backtesting; SA adds Breakdown)
- **Reconciliation strip** over each attribution table (rows shown, Σ shown vs
  node total, coverage, rows needing review)
- Attribution tables with reconciliation filters (all / reconciled / needs review)
- Diagnostics tab surfacing unsupported / residual records and provisional flags
- Provisional figures (e.g. PLA add-on) flagged as indicative rather than shown as a fail-closed zero
- **Deep-linkable view state** — run, node, tab, and filters are encoded in the URL
- Companion rail: capital mix + run-health metrics
- Same visual language as `tools/onboarding_mapper`

## Next phases

- **P1:** `frtb-result-store` adapter for committed Parquet/DuckDB runs
- **P2:** Movements, regime comparison, impact analysis
- **P3:** CVA panels and full suite orchestration views
