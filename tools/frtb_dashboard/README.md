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

## MVP (P0) capabilities

- Synthetic **demo-suite-001** run built from public package fixtures and demos
- Top-of-house KPIs: suite, IMA, SA totals
- Capital tree navigation (IMA desk → IMCC / SES / PLA measures; SA → SBM / DRC / RRAO)
- IMA desk panels: IMCC, SES/NMRF (stress period + method selection), PLA, backtesting, attribution
- SA component breakdown with top attribution rows
- Same visual language as `tools/onboarding_mapper`

## Next phases

- **P1:** `frtb-result-store` adapter for committed Parquet/DuckDB runs
- **P2:** Movements, regime comparison, impact analysis
- **P3:** CVA panels and full suite orchestration views
