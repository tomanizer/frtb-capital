# Capital Navigator implementation slices

Status: draft implementation plan for issue #1111.

Audience: Capital Navigator frontend/backend implementers, result-store
contributors, reviewers, and agents planning focused PRs.

Related:

- Parent split epic: #1106
- Result-store delivery epic: #1105
- UX contract:
  [`UX_AUDIT_AND_INTERACTION_CONTRACT.md`](UX_AUDIT_AND_INTERACTION_CONTRACT.md)
- State and routing contract:
  [`NAVIGATOR_STATE_AND_ROUTING.md`](NAVIGATOR_STATE_AND_ROUTING.md)
- Result-store data contract:
  [`RESULT_STORE_DATA_CONTRACT.md`](RESULT_STORE_DATA_CONTRACT.md)
- Capital and movement semantics:
  [`CAPITAL_AND_MOVEMENT_SEMANTICS.md`](CAPITAL_AND_MOVEMENT_SEMANTICS.md)
- Mode wireframes:
  [`MODE_WIREFRAMES.md`](MODE_WIREFRAMES.md)
- AI explanation contract:
  [`AI_EXPLANATION_CONTRACT.md`](AI_EXPLANATION_CONTRACT.md)

This document turns the Capital Navigator contracts into reviewable delivery
slices. It is not a project-management chart and it does not implement runtime
features. Each slice should normally be one focused PR. Do not bundle all modes
into one implementation PR.

This plan is binding for delivery sequencing and validation expectations. The
later production capabilities called out as blocked by #1105 child issues are
future/runtime dependencies, not permission to bundle those result-store changes
into the first UI PRs.

## Delivery Rules

- Keep runtime UI changes separate from result-store contract/runtime changes
  unless a slice explicitly needs both to prove an integration boundary.
- Prefer fixture-backed behavior before production-scale adapters.
- Preserve the source-of-truth rule: the browser may display, filter, sort, and
  route supplied values, but it must not recompute capital, official subtotals,
  attribution, RFET/SES, PLA, CVA, source-row totals, or binding status.
- Use stable `NavigatorState` and result-store IDs in every slice that touches
  routing, caching, selected rows, source rows, or explanation snapshots.
- Every PR should state which slice it implements and which later slices remain
  out of scope.

## Slice Index

| Slice | Primary outcome | Result-store dependency | Typical PR scope |
| --- | --- | --- | --- |
| 1. Shell cleanup and collapsible hierarchy | Current dashboard becomes easier to navigate without new data | None | Frontend-only plus docs/tests |
| 2. `NavigatorState`, URL state, and cache keys | One shareable state model prevents stale rows/evidence | None | Frontend state/API adapter tests |
| 3. Honest controls and no-data states | Controls stop implying unavailable functionality exists | Existing fixture payloads; explicit no-data payloads improve quality | Frontend/backend fixture shaping |
| 4. Result-store adapter boundary | Dashboard has a thin adapter contract over result-store/public APIs | Existing surfaces in #1105; production use grows with #1074/#1075/#1101/#1102/#1103/#1104 | Backend adapter/docs/tests |
| 5. Movement MVP | Users can rank and inspect current-vs-baseline movement | Movement rows from existing fixture first; richer result-store movement under #1105 | Backend fixture plus frontend grid |
| 6. Inspector redesign | Evidence review becomes decisive and row-scoped | Existing attribution/source rows; artifact paging later from #1074/#1075 | Frontend inspector plus backend filtering |
| 7. Component drilldowns | SA, IMA, CVA component views have natural drill paths | Existing component marts where available; CVA/RFET/PLA gaps explicit | Focused component UI/backend slices |
| 8. RFET/NMRF/SES mode | Risk-factor modellability and SES become first-class | Blocked for production by #1101; artifact drillthrough by #1074/#1075 | Fixture prototype then result-store integration |
| 9. PLA desk eligibility mode | Desk eligibility/PLA/backtesting becomes first-class | Blocked for production by #1102; P&L artifact pages by #1074/#1075 | Fixture prototype then result-store integration |
| 10. Risk-factor and time-series drivers | Risk-factor movement links to books/desks/capital rows | Depends on #1074/#1075; RFET/SES fields depend on #1101 | Metadata/time-series UI plus adapter |
| 11. Pivot drawer and hierarchy aggregation | Pivots stay reconciled and label display-only totals | Official server-side pivots blocked by #1103 | Frontend shell first, official aggregates later |
| 12. Governed AI explanation drawer | Commentary is evidence-linked, auditable, and bounded | Snapshot builder blocked by #1104 | UI shell/schema first, model call out of scope |

## Slice 1: Shell Cleanup and Collapsible Hierarchy

Goal: make the current dashboard usable as a dense workbench before adding new
analytical modes.

Prerequisites:

- Current `tools/frtb_dashboard` fixture app runs.
- `MODE_WIREFRAMES.md` shell anatomy is accepted.

Result-store dependency:

- None. This slice must improve the current fixture UX without new
  `frtb-result-store` runtime work.

Files likely touched:

- `tools/frtb_dashboard/frontend/src/App.tsx`
- `tools/frtb_dashboard/frontend/src/index.css`
- `tools/frtb_dashboard/frontend/src/types.ts`
- `tools/frtb_dashboard/frontend/src/api.ts` only if hierarchy metadata shape
  needs a display-only field.

Fixture needs:

- Existing hierarchy fixture is enough.
- Add only synthetic display metadata needed for collapse badges or node type
  labels.

Tests:

- Frontend component/state tests for expanded, compact, and hidden rail state
  where the frontend test harness exists.
- Backend smoke tests only if fixture metadata changes.
- Manual browser verification for desktop and compact/mobile widths.

Validation commands:

- `make agent-guard`
- `make docs-check` if docs are touched
- affected frontend test command from `tools/frtb_dashboard/frontend/package.json`
- `uv run python tools/frtb_dashboard/run.py --port <port>` plus browser smoke
  for shell layout

Non-goals:

- No new result-store APIs.
- No new analytical rows.
- No pivot, AI, RFET, PLA, or movement semantics.

## Slice 2: `NavigatorState`, URL State, and Cache Keys

Goal: prevent stale evidence by driving run, scope, mode, framework, scenario,
baseline, grid, selected object, filters, and inspector state from one explicit
state object.

Prerequisites:

- Slice 1 shell layout or an equivalent stable shell.
- `NAVIGATOR_STATE_AND_ROUTING.md` accepted as canonical state contract.

Result-store dependency:

- None. This slice can wrap current fixture endpoints and cache keys.

Files likely touched:

- `tools/frtb_dashboard/frontend/src/App.tsx`
- `tools/frtb_dashboard/frontend/src/api.ts`
- `tools/frtb_dashboard/frontend/src/types.ts`
- frontend route/state helper files if split from `App.tsx`
- backend request parsing only where current query parameters are incomplete.

Fixture needs:

- Existing single-run fixture is enough for route restoration.
- Optional second synthetic run only if baseline URL fields are rendered in this
  slice.

Tests:

- URL serializer/parser round-trip tests.
- Reset-rule tests for scope, framework, scenario, grid mode, selected row, and
  inspector tab.
- Cache-key tests proving stale grid/inspector requests do not reuse
  incompatible state.

Validation commands:

- `make agent-guard`
- frontend test command for state helpers
- targeted backend tests for changed query parsing
- `make docs-check` when state docs are updated

Non-goals:

- No production result-store adapter.
- No new analytical modes beyond routing placeholders.
- No browser-local recomputation of capital or movement.

## Slice 3: Honest Controls and No-Data States

Goal: every visible control either works for the current run/scope or explains
why it is unavailable.

Prerequisites:

- Slice 2 state model, or an explicit interim state compatibility layer.
- No-data/state taxonomy from `CAPITAL_AND_MOVEMENT_SEMANTICS.md`.

Result-store dependency:

- Can start with current fixture diagnostics.
- Production completeness should reuse explicit availability states from #1105
  and artifact/no-data records from #1074/#1075.

Files likely touched:

- `tools/frtb_dashboard/frontend/src/App.tsx`
- `tools/frtb_dashboard/frontend/src/types.ts`
- `tools/frtb_dashboard/backend/models.py`
- `tools/frtb_dashboard/backend/demo_runs.py`
- `tools/frtb_dashboard/backend/app.py`

Fixture needs:

- At least one unavailable baseline state.
- CVA no-data, unsupported component, partial source, and synthetic data
  diagnostics.
- Multiple-run fixture only if run selector is made active.

Tests:

- Backend view-model tests for `NO_DATA`, `UNSUPPORTED`, `STALE`, `PARTIAL`,
  and `SYNTHETIC` states.
- Frontend tests that hidden/disabled controls do not mutate state.
- Regression for missing CVA rendering as no-data, not zero.

Validation commands:

- `make agent-guard`
- targeted dashboard backend tests
- affected frontend tests
- `make docs-check`

Non-goals:

- No baseline movement calculations unless included in Slice 5.
- No production entitlement model.

## Slice 4: Result-Store Adapter Boundary

Goal: introduce a thin dashboard adapter boundary that maps `NavigatorState` to
result-store/public API calls while preserving fixture compatibility.

Prerequisites:

- Slice 2 state model.
- `RESULT_STORE_DATA_CONTRACT.md` accepted.

Result-store dependency:

- Existing result-store capital tree, component, movement, attribution,
  hierarchy, artifact, and mart surfaces where present.
- Production metadata/time-series behavior depends on #1074 and #1075.
- RFET/PLA/pivot/AI production behavior remains blocked by #1101, #1102,
  #1103, and #1104 respectively.

Files likely touched:

- `tools/frtb_dashboard/backend/app.py`
- `tools/frtb_dashboard/backend/models.py`
- new dashboard adapter module under `tools/frtb_dashboard/backend/`
- result-store public docs only if a public contract gap is discovered
- focused tests under dashboard and/or `packages/frtb-result-store/tests`.

Fixture needs:

- Synthetic adapter fixtures that preserve result-store IDs:
  `run_id`, `node_id`, `artifact_id`, `attribution_id`, `desk_id`,
  `risk_factor_id`, and hierarchy node IDs where available.

Tests:

- Adapter maps `NavigatorState` to expected backend/result-store calls.
- No-data and unsupported states are passed through without browser inference.
- Stale response/cancellation behavior is testable at the adapter boundary.

Validation commands:

- `make agent-guard`
- targeted dashboard backend tests
- targeted `frtb-result-store` tests if package code changes
- `make quality-control` for runtime or contract changes

Non-goals:

- No generic SQL endpoint.
- No direct browser reads of DuckDB, Parquet, S3, or artifact files.
- No migration of capital calculations into result store.

## Slice 5: Movement MVP

Goal: make the dashboard answer "what changed?" for the selected run, baseline,
scope, framework, and row.

Prerequisites:

- Slice 2 state model.
- Slice 3 no-baseline/no-data behavior.
- Capital and movement semantics accepted.

Result-store dependency:

- Start with a synthetic baseline fixture and existing movement summary where
  available.
- Production movement should consume #1105 movement rows and artifact lineage.

Files likely touched:

- `tools/frtb_dashboard/backend/demo_runs.py`
- `tools/frtb_dashboard/backend/models.py`
- `tools/frtb_dashboard/backend/app.py`
- `tools/frtb_dashboard/frontend/src/App.tsx`
- `tools/frtb_dashboard/frontend/src/types.ts`

Fixture needs:

- Current and baseline run with identical semantic row IDs.
- Examples for no baseline, new row, dropped row, near-zero baseline, and
  restated baseline if supported.

Tests:

- Movement amount, percent suppression, new/dropped/no-baseline states.
- Grid sorting by absolute movement and percent movement.
- Inspector shows current, baseline, movement, source, and limitation for the
  selected row.

Validation commands:

- `make agent-guard`
- targeted dashboard backend tests
- affected frontend tests
- `make docs-check`
- `make quality-control` if backend contracts change

Non-goals:

- No multi-baseline comparison.
- No statistical outlier model.
- No browser-side official subtotal or attribution recomputation.

## Slice 6: Inspector Redesign

Goal: make the inspector the evidence surface for the selected row rather than a
generic JSON/detail dump.

Prerequisites:

- Slice 2 selection reset rules.
- Slice 3 no-data/diagnostic taxonomy.
- Row-scoped evidence requirements from the wireframes.

Result-store dependency:

- Can start with existing attribution/source diagnostics in the fixture.
- Bounded source-row/artifact paging should align with #1074/#1075 when
  production artifact pages are needed.

Files likely touched:

- `tools/frtb_dashboard/frontend/src/App.tsx`
- `tools/frtb_dashboard/frontend/src/types.ts`
- `tools/frtb_dashboard/backend/app.py`
- `tools/frtb_dashboard/backend/models.py`

Fixture needs:

- DRC bucket with bucket-scoped source rows.
- IMA desk with model evidence, PLA/backtesting summary, and NMRF/SES warning.
- RRAO row with classification evidence.

Tests:

- Inspector clears or reloads when selected row/scope/framework changes.
- Source rows are row-scoped, not component-wide.
- Empty tabs are hidden or shown only with meaningful no-data reasons.
- Diagnostics sort by materiality.

Validation commands:

- `make agent-guard`
- targeted dashboard backend tests
- affected frontend tests
- `make docs-check`

Non-goals:

- No AI explanation generation.
- No high-volume source-row browser beyond bounded fixture pages.

## Slice 7: Component Drilldowns

Goal: provide natural first drill paths for SA, IMA, and CVA views without
mixing every component's controls into one table.

Prerequisites:

- Slice 2 state model.
- Slice 6 inspector tabs and row-scoped evidence.
- `MODE_WIREFRAMES.md` component mode anatomy.

Result-store dependency:

- SBM/DRC/RRAO can start from current component rows and package-derived
  fixtures.
- CVA remains explicit no-data/unsupported until result-store/package payloads
  exist for the selected scope.
- RFET/PLA details link out to slices 8 and 9 rather than being implemented
  here.

Files likely touched:

- `tools/frtb_dashboard/frontend/src/App.tsx`
- `tools/frtb_dashboard/frontend/src/types.ts`
- `tools/frtb_dashboard/backend/demo_runs.py`
- `tools/frtb_dashboard/backend/models.py`
- component-specific fixture adapters under `tools/frtb_dashboard/backend/`.

Fixture needs:

- SBM risk class/measure/bucket rows with scenario values.
- DRC bucket/issuer rows with source evidence.
- RRAO category/classification rows.
- CVA calculated, no-exposure, feed-missing, and unsupported examples where
  supported by fixtures.

Tests:

- Scenario selection applies only to SBM-supported rows.
- DRC issuer drilldown reconciles to bucket rows.
- RRAO classification detail preserves inclusion/exclusion state.
- CVA no-data is not rendered as zero.

Validation commands:

- `make agent-guard`
- targeted dashboard backend tests
- affected frontend tests
- `make docs-check`
- `make quality-control` if runtime adapter/package contracts change

Non-goals:

- No full CRIF/source-row browser.
- No production CVA/XVA analytics.
- No formula-internal grids for every component.

## Slice 8: RFET/NMRF/SES Mode

Goal: make risk-factor modellability, NMRF state, SES contribution, and
desk/book usage first-class Navigator surfaces.

Prerequisites:

- Slice 2 state model with `analysisMode=rfet_nmrf` and `riskFactorId`.
- Slice 6 inspector structure.
- IMA/risk-factor metadata fixture coverage sufficient for a prototype.

Result-store dependency:

- Production implementation is blocked by #1101.
- Observation/source drillthrough depends on #1074/#1075 for artifact schemas
  and bounded time-series APIs.

Files likely touched:

- `tools/frtb_dashboard/frontend/src/App.tsx`
- `tools/frtb_dashboard/frontend/src/types.ts`
- `tools/frtb_dashboard/backend/models.py`
- `tools/frtb_dashboard/backend/app.py`
- fixture adapters that expose risk-factor evidence.

Fixture needs:

- One modellable factor.
- One non-modellable SES-driving factor.
- One stale/missing-evidence factor.
- One no-data or unsupported risk-factor state.
- Usage mapping to book, desk, business line, legal entity, and top-of-house
  where available.

Tests:

- Stable `riskFactorId` selection across RFET, IMA, and source views.
- Filtering by hierarchy node, desk/book, risk class, and risk factor.
- SES bridge displays supplied amounts and movements only.
- No-data/stale/unsupported states are distinct.

Validation commands:

- `make agent-guard`
- targeted dashboard backend tests
- affected frontend tests
- targeted `frtb-result-store` tests when #1101 integration lands
- `make quality-control` for result-store/runtime changes

Non-goals:

- No RFET or SES recalculation in dashboard/result store.
- No production market-data store.
- No raw observation dump by default.

## Slice 9: PLA Desk Eligibility Mode

Goal: make desk eligibility, PLA/backtesting state, RFET/NMRF summary, SES, and
capital consequence visible without JSON diving.

Prerequisites:

- Slice 2 state model with `analysisMode=pla` and `deskId`.
- Slice 6 inspector structure.
- IMA fixture evidence for at least one desk.

Result-store dependency:

- Production implementation is blocked by #1102.
- P&L vector/source artifact drillthrough depends on #1074/#1075.

Files likely touched:

- `tools/frtb_dashboard/frontend/src/App.tsx`
- `tools/frtb_dashboard/frontend/src/types.ts`
- `tools/frtb_dashboard/backend/models.py`
- `tools/frtb_dashboard/backend/app.py`
- IMA fixture adapter code if desk evidence is reshaped.

Fixture needs:

- One eligible desk.
- One amber/red desk.
- One not-run or no-data desk.
- One desk with RFET/NMRF/SES linkage and capital consequence.

Tests:

- Eligibility, PLA, and backtesting state taxonomy.
- Filtering by hierarchy, desk, eligibility state, PLA state, and backtesting
  state.
- Capital consequence uses supplied backend/result-store values.
- Inspector links failing tests to affected books/risk factors where supplied.

Validation commands:

- `make agent-guard`
- targeted dashboard backend tests
- affected frontend tests
- targeted `frtb-result-store` tests when #1102 integration lands
- `make quality-control` for result-store/runtime changes

Non-goals:

- No PLA/backtesting calculation in result store.
- No official regulatory desk approval workflow.
- No unbounded P&L vector storage in grid rows.

## Slice 10: Risk-Factor and Time-Series Drivers

Goal: rank risk factors by movement/outlier evidence and link them to books,
desks, model evidence, and capital rows.

Prerequisites:

- Slice 5 movement state.
- Slice 8 risk-factor IDs and usage mapping when RFET/SES fields are included.
- Time-window state from `NAVIGATOR_STATE_AND_ROUTING.md`.

Result-store dependency:

- Time-series metadata and points are blocked by #1074/#1075.
- RFET/SES driver fields are blocked by #1101.

Files likely touched:

- `tools/frtb_dashboard/frontend/src/App.tsx`
- `tools/frtb_dashboard/frontend/src/types.ts`
- `tools/frtb_dashboard/backend/models.py`
- `tools/frtb_dashboard/backend/app.py`
- dashboard adapter methods for metadata/time-series calls.

Fixture needs:

- Current and baseline risk-factor values.
- At least one capital movement linked to a risk factor.
- Time-series point sample with current, baseline, RFET gap, and SES markers
  where available.

Tests:

- Driver classification: market-data, exposure/sensitivity, model evidence,
  aggregation, source-data, or unsupported/no-data.
- Time-window selection updates grid and inspector consistently.
- Risk-factor selection links to affected books/desks and capital rows without
  changing scope unexpectedly.

Validation commands:

- `make agent-guard`
- targeted dashboard backend tests
- affected frontend tests
- targeted `frtb-result-store` tests when #1074/#1075 integration lands
- `make quality-control` for runtime contract changes

Non-goals:

- No multi-series charting by default.
- No interpolation, pricing, or market-data sourcing.
- No browser-side outlier model beyond supplied or documented fixture metrics.

## Slice 11: Pivot Drawer and Hierarchy Aggregation

Goal: let users reshape views without creating unlabelled, unreconciled, or
browser-official subtotals.

Prerequisites:

- Slice 2 state model with `pivotRows`, `pivotColumns`, filters, and sort.
- Slice 5 movement columns if movement pivots are included.
- `MODE_WIREFRAMES.md` pivot anatomy.

Result-store dependency:

- Official server-side aggregate pivots are blocked by #1103.
- Before #1103, the UI may expose display-only grouping only if every subtotal
  row is labelled `display-only`.

Files likely touched:

- `tools/frtb_dashboard/frontend/src/App.tsx`
- `tools/frtb_dashboard/frontend/src/types.ts`
- `tools/frtb_dashboard/backend/models.py`
- `tools/frtb_dashboard/backend/app.py`
- dashboard adapter for pivot query parameters.

Fixture needs:

- Hierarchy/component pivot rows.
- Movement by hierarchy/component if Slice 5 exists.
- RFET/PLA pivots only after slices 8 and 9 have fixture rows.

Tests:

- Pivot URL round-trip.
- Invalid row/column/filter combinations fail closed.
- Official and display-only subtotal flags render distinctly.
- Paging and deterministic ordering for pivot rows.

Validation commands:

- `make agent-guard`
- targeted dashboard backend tests
- affected frontend tests
- targeted `frtb-result-store` tests when #1103 integration lands
- `make quality-control` for result-store/runtime changes

Non-goals:

- No spreadsheet clone.
- No arbitrary calculated fields.
- No official totals computed only from currently visible browser rows.

## Slice 12: Governed AI Explanation Drawer

Goal: add the explanation UI contract without weakening auditability, evidence
discipline, or source-data controls.

Prerequisites:

- Slice 2 state model.
- Slice 6 inspector evidence tabs.
- `AI_EXPLANATION_CONTRACT.md` from issue #1112.

Result-store dependency:

- Production snapshot construction is blocked by #1104.
- Until #1104 lands, the UI may render disabled/placeholder explanation actions
  with precise dependency reasons.

Files likely touched:

- `tools/frtb_dashboard/frontend/src/App.tsx`
- `tools/frtb_dashboard/frontend/src/types.ts`
- `tools/frtb_dashboard/backend/models.py`
- optional backend placeholder route for disabled-state/schema validation.

Fixture needs:

- Frozen synthetic explanation snapshots only if they are explicitly labelled as
  fixtures.
- Evidence references for row, desk, risk factor, source row, diagnostic, and
  artifact examples.

Tests:

- Request schema validation for target type, style, depth, and selected object.
- Evidence chips route back to supplied IDs.
- Limitation-first rendering for no-data, partial, unsupported, stale, and
  synthetic snapshots.
- Negative/refusal scenarios from `AI_EXPLANATION_CONTRACT.md`.

Validation commands:

- `make agent-guard`
- targeted dashboard backend tests for schema/placeholder routes
- affected frontend tests
- targeted `frtb-result-store` tests when #1104 integration lands
- `make quality-control` for runtime contract changes

Non-goals:

- No API keys, provider credentials, or model calls.
- No browser-constructed authoritative prompt payloads.
- No generated explanation as regulatory evidence or capital calculation.

## Cross-Slice Validation Expectations

Use the narrowest validation that proves the changed behavior, then widen for
runtime or shared-contract changes.

Documentation-only slice PRs:

- `make agent-guard`
- `make docs-check`
- targeted markdown link check when adding or renaming docs
- `git diff --check`

Frontend-only fixture UI PRs:

- `make agent-guard`
- affected frontend lint/test/build commands from
  `tools/frtb_dashboard/frontend/package.json`
- dashboard backend smoke if API request shapes change
- browser smoke for the changed workflow

Dashboard backend or adapter PRs:

- `make agent-guard`
- targeted dashboard backend tests
- affected frontend tests for changed view models
- `make quality-control`

Result-store runtime PRs:

- `make agent-guard`
- targeted `packages/frtb-result-store/tests/...`
- `make ci-local-pr` when runtime contracts, marts, storage schemas, or public
  APIs change
- `make quality-control`

## Dependency Checklist

- Slices 1 and 2 are intentionally unblocked by new result-store runtime work.
- Slices 3 through 7 can use current synthetic fixtures but must render missing
  result-store evidence honestly.
- Slice 8 production readiness depends on #1101 and may need #1074/#1075 for
  observation drillthrough.
- Slice 9 production readiness depends on #1102 and may need #1074/#1075 for
  P&L artifact pages.
- Slice 10 depends on #1074/#1075 for time-series drivers and #1101 for RFET/SES
  fields.
- Slice 11 official aggregate semantics depend on #1103.
- Slice 12 production snapshots depend on #1104 and the issue #1112 AI contract.

## Acceptance Checklist

- Each slice is small enough for a focused PR.
- Each slice names prerequisites, result-store dependencies, likely files,
  fixture needs, tests, validation commands, and non-goals.
- Blockers from #1105 child issues are explicit.
- First two slices improve the current UX without new result-store runtime.
- The plan makes clear that all modes must not be bundled into one PR.
