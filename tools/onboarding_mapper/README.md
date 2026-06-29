# FRTB Onboarding Mapper

Interactive web application for onboarding client datasets onto FRTB canonical Arrow
input table contracts. Load client CSV, Parquet, Arrow IPC, server paths, or DuckDB
queries, map columns to package `ColumnSpec` definitions, validate through the
public normalizers, and export a reusable `mapping.yaml`, `mapping.toml`, or
`mapping.json` artifact for ingestion pipelines.

## Quick start

From the repository root:

```bash
# Terminal 1 — API (serves built frontend when dist/ exists)
uv run --with uvicorn python tools/onboarding_mapper/run.py --reload --port 8765

# Terminal 2 — frontend dev server with API proxy
cd tools/onboarding_mapper/frontend
npm install
npm run dev
```

Open http://localhost:5173 during development, or http://127.0.0.1:8765 after
`npm run build` when the API serves the static bundle.

Production-style single-server run:

```bash
cd tools/onboarding_mapper/frontend && npm install && npm run build
cd ../../.. && uv run --with uvicorn python tools/onboarding_mapper/run.py --port 8765
```

## Workflow

1. **Target dataset** — choose a canonical input table from DRC, SBM, RRAO, CVA, or IMA.
2. **Client source** — upload or load the client table (CSV / Parquet / Arrow IPC / DuckDB SQL).
3. **Column mapping** — map each canonical column to a client column; use auto-suggest for names and aliases.
4. **Validate & export** — run the package normalizer, preview accepted rows, download mapping config.

## Mapping artifact

Example `frtb_drc.nonsec.mapping.yaml`:

```yaml
version: "1"
target:
  package: frtb_drc
  input_table: nonsec
  component: DRC
  label: DRC non-securitisation
source:
  connector: file
  format: parquet
  path: /data/client/drc_positions.parquet
column_mapping:
  issuer_id: ISSUER
  notional: EXPOSURE
  position_id: POS_ID
lineage:
  source_system: client_etl
  source_file: drc_positions.parquet
  source_column_map:
    - - EXPOSURE
      - notional
    - - ISSUER
      - issuer_id
    - - POS_ID
      - position_id
```

The `column_mapping` block is canonical-name → client-column. The `lineage.source_column_map`
pairs follow the suite lineage convention (client source, canonical target).

## Scope

This tool is onboarding and contract-mapping assistance only. Validation uses public
package normalizers and does not calculate regulatory capital. Outputs are not
final regulatory capital.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/tables` | List canonical input tables |
| `GET /api/tables/{package}/{id}` | Column spec detail |
| `POST /api/source/upload` | Upload client file |
| `POST /api/source/path` | Load server-side file path |
| `POST /api/source/duckdb` | Execute DuckDB query |
| `POST /api/mapping/suggest` | Auto-suggest column mapping |
| `POST /api/mapping/validate` | Normalize mapped table |
| `POST /api/mapping/export` | Generate mapping artifact |
