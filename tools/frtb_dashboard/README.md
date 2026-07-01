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

## What the viewer inspects

The static shell is scoped to metadata evidence for one committed run. In the
current implementation it selects rows directly from the metadata catalogs; the
full Capital Navigator contract later drives these same metadata tabs from the
active capital row and its lineage.

- time-series catalogs and paged points;
- shock-definition catalogs and paged rows;
- scenario-vector metadata catalogs and paged rows;
- surface catalogs and filtered surface slices;
- artifact availability states: `AVAILABLE`, `NO_DATA`, and `UNSUPPORTED`;
- artifact-row lineage/provenance fields for inspection.

It intentionally does not implement the production OLAP backend, AG Grid
Enterprise, entitlements, market-data sourcing, shock generation, surface
interpolation, RFET vendor remediation, or capital calculation. Those remain
outside this static viewer and are documented as boundaries in ADRs 0049-0052.

For the result-store schema and endpoint guide, see
`docs/modules/frtb-result-store/ARTIFACT_METADATA.md`.
