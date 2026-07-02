# AGENTS.md - frtb-navigator

`frtb-navigator` is a read-only application/read-model package for inspecting
already-resolved FRTB capital results. It is not a capital calculation component.

## Boundaries

- Do not calculate capital in this package.
- Do not classify regulatory inputs in the browser.
- Do not fetch raw object-store files directly.
- Do not generate shocks, interpolate surfaces, or synthesize missing rows.
- Do not silently substitute zero for missing scoped rows.
- Consume result-store and orchestration read models, then display explicit
  `NO_DATA` or `UNSUPPORTED` states when payloads are unavailable.
- Rendering, filtering, frontend caching, and inspection of already-resolved
  API/read-model payloads are in scope.
- Time-series, shock, scenario-vector, and surface metadata boundaries are
  governed by
  [`../../docs/ARTIFACT_METADATA_OWNERSHIP.md`](../../docs/ARTIFACT_METADATA_OWNERSHIP.md);
  Navigator renders backend/API payloads and no-data states only.

## Validation

- Backend: `uv run pytest packages/frtb-navigator/tests`
- Frontend: `cd packages/frtb-navigator/frontend && npm install && npm run build`
- Package import: `uv run python -c "import frtb_navigator"`
