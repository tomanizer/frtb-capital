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
3. **Column mapping** — map each canonical column to a client column. Auto-suggest
   matches names in decreasing-confidence tiers — exact, case-insensitive,
   normalized (separator/casing style, so `position_id` ↔ `positionId` ↔
   `POSITION-ID`), then identical token set — and stays conservative: it does not
   expand abbreviations or guess by edit distance, so anything it cannot match
   structurally is left for you to set manually.
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

Reusing a saved mapping: load a previously exported `mapping.yaml` / `.toml` /
`.json` from the **Import mapping** control on the target-dataset step. The tool
parses the artifact, re-selects the target contract, and restores the
`column_mapping` (warning about any fields no longer in the contract) so you can
re-validate it against a fresh client extract.

## Security and configuration

This is a **local, single-operator tool** that reads server-side files and runs
DuckDB SQL. Bind it to loopback (the default `--host 127.0.0.1`) and do not
expose it on a shared network. Behaviour is constrained by environment variables
(all optional):

| Variable | Default | Purpose |
| --- | --- | --- |
| `FRTB_ONBOARDING_ALLOW_ORIGINS` | dev + self-served origins | Comma-separated CORS allowlist (`*` to disable the check — not recommended). |
| `FRTB_ONBOARDING_DATA_ROOTS` | repository root | `os.pathsep`-separated directories the `path` and DuckDB `attach` connectors may read. Requests outside these roots return HTTP 403. |
| `FRTB_ONBOARDING_MAX_UPLOAD_MB` | `1024` | Upload size cap; larger bodies return HTTP 413. |
| `FRTB_ONBOARDING_MAX_SESSIONS` | `24` | Retained client sessions (LRU eviction beyond this). |
| `FRTB_ONBOARDING_SESSION_TTL_SECONDS` | `3600` | Idle session lifetime before eviction. |

CORS defaults to the dev server and self-served origins only, so a stray web page
cannot drive the file/DuckDB connectors. The DuckDB connector still executes
arbitrary SQL within the data roots; only expose it in trusted local use.

## Scope

This tool is onboarding and contract-mapping assistance only. Validation uses public
package normalizers and does not calculate regulatory capital. Outputs are not
final regulatory capital.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/tables` | List canonical input tables |
| `GET /api/tables/{package}/{id}` | Column spec detail |
| `POST /api/source/upload` | Upload client file (size-capped) |
| `POST /api/source/path` | Load server-side file path (sandboxed to data roots) |
| `POST /api/source/duckdb` | Execute DuckDB query (attach targets sandboxed) |
| `POST /api/mapping/suggest` | Auto-suggest column mapping |
| `POST /api/mapping/validate` | Normalize mapped table |
| `POST /api/mapping/export` | Generate mapping artifact |
| `POST /api/mapping/import` | Parse a saved mapping artifact back into state |
