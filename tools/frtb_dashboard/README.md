# FRTB Capital Navigator metadata viewer

This is a dependency-free static shell for the Capital Navigator metadata
inspection flow from issue #1080. It is intentionally small: it consumes the
read-only `frtb-result-store` FastAPI metadata endpoints and does not calculate
capital, fetch raw object-store files, generate shocks, interpolate surfaces,
or synthesize missing rows.

## Run

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

The UI expects the metadata contract documented in
`docs/modules/frtb-result-store/CAPITAL_NAVIGATOR_METADATA_CONTRACT.md`.
