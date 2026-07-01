# FRTB Capital Navigator State and Routing Contract

Status: draft implementation contract for issue #1107.

Audience: Capital Navigator frontend/backend implementers, result-store adapter
authors, and reviewers.

Related:

- Epic: #1106
- UX north star: `docs/tools/frtb-dashboard/UX_AUDIT_AND_INTERACTION_CONTRACT.md`
- Result-store epic: #1105

## 1. Purpose

The Capital Navigator should behave like one stable analytical workbench. Users
change run, scope, mode, framework, scenario, pivot, or selected object; the
capital strip, grid, inspector, artifact pages, and AI explanation drawer update
from that state without showing stale evidence.

This document defines the frontend state machine, URL contract, cache-key rules,
and state-to-query mapping. It does not define result-store response schemas;
those belong in `RESULT_STORE_DATA_CONTRACT.md`.

## 2. Current State

The current v2 fixture app keeps a small set of React state values:

```text
framework
scenario
selectedNodeId
selectedRowId
expanded
query
activeInspectorTab
loadingZone
error
```

It also uses local in-memory cache keys for run, metadata, grid, and inspector
requests. That is adequate for the demo fixture, but the target Navigator needs
state that can represent hierarchy scope, analysis mode, baseline movement,
desk/risk-factor selection, pivots, artifact pages, and explanation snapshots.

## 3. Canonical NavigatorState

Target state:

```text
NavigatorState
  runId: string
  baselineRunId: string | null
  hierarchyNodeId: string
  analysisMode: capital | hierarchy | desk | sa | ima | cva | pla | rfet_nmrf | risk_factor | pivot
  framework: Binding | SA | IMA | CVA
  scenario: Binding | Base | High | Low
  timeWindow: current | prior_run | prior_business_day | month_end | quarter_end | year_on_year | custom
  gridMode: capital_stack | drivers | evidence | source_rows | eligibility | rfet_register | time_series | pivot
  rowId: string | null
  deskId: string | null
  riskFactorId: string | null
  artifactId: string | null
  inspectorTab: summary | attribution | source | model | diagnostics | lineage | explanation
  explanationId: string | null
  pivotRows: string[]
  pivotColumns: string[]
  filters: FilterSpec[]
  hierarchySearch: string
  gridSearch: string
  sort: SortSpec[]
  columnPreset: capital | movement | evidence | source | compact
  artifactPage: PageSpec | null
```

Supporting shapes:

```text
FilterSpec
  field: string
  op: eq | in | contains | range | state
  value: string | number | boolean | string[] | number[]

SortSpec
  field: string
  direction: asc | desc

PageSpec
  artifactId: string
  limit: number
  offset: number
  columns: string[]
  filters: FilterSpec[]
```

## 4. State Ownership

| State | URL | Server query | Local storage | Ephemeral only |
| --- | --- | --- | --- | --- |
| `runId` | yes | yes | no | no |
| `baselineRunId` | yes | yes | no | no |
| `hierarchyNodeId` | yes | yes | last-used optional | no |
| `analysisMode` | yes | yes | last-used optional | no |
| `framework` | yes | yes | last-used optional | no |
| `scenario` | yes | yes | no | no |
| `timeWindow` | yes | yes | last-used optional | no |
| `gridMode` | yes | yes | last-used optional | no |
| `rowId` | yes | yes for inspector | no | no |
| `deskId` | yes | yes | no | no |
| `riskFactorId` | yes | yes | no | no |
| `artifactId` | yes | yes | no | no |
| `inspectorTab` | yes | no | no | no |
| `explanationId` | yes, if snapshot-valid | yes | no | no |
| `pivotRows` | yes | yes | last-used optional | no |
| `pivotColumns` | yes | yes | last-used optional | no |
| `filters` | yes | yes | no | no |
| `hierarchySearch` | no | no | no | yes |
| `gridSearch` | optional | yes if server-side | no | no |
| `sort` | yes | yes | last-used optional | no |
| `columnPreset` | yes | yes | yes | no |
| hierarchy rail collapsed/width | no | no | yes | no |
| loading/error/abort controllers | no | no | no | yes |

Rules:

- URL state must be enough to restore the analytical view.
- Local storage may improve ergonomics, but it must not change query semantics
  silently.
- Ephemeral state must never be required to reproduce a finding.

## 5. URL Contract

The route should be shareable and stable:

```text
/navigator/:runId
```

Core query parameters:

| Parameter | State | Example |
| --- | --- | --- |
| `baseline` | `baselineRunId` or baseline alias | `prev-month` |
| `scope` | `hierarchyNodeId` | `book-rates-fixture` |
| `mode` | `analysisMode` | `rfet_nmrf` |
| `framework` | `framework` | `SA` |
| `scenario` | `scenario` | `High` |
| `window` | `timeWindow` | `month_end` |
| `grid` | `gridMode` | `drivers` |
| `row` | `rowId` | `sa-drc-corporate` |
| `desk` | `deskId` | `rates-credit-demo` |
| `riskFactor` | `riskFactorId` | `rf-girr-usd-5y` |
| `artifact` | `artifactId` | `artifact-id` |
| `tab` | `inspectorTab` | `source` |
| `explanation` | `explanationId` | `exp-123` |
| `rows` | `pivotRows` | `hierarchy,component` |
| `cols` | `pivotColumns` | `scenario` |
| `filter` | repeated filter specs | `component=SBM` |
| `sort` | sort specs | `movement:desc` |
| `columns` | `columnPreset` | `movement` |

Filter syntax in URLs should stay simple:

```text
filter=<field>:<op>:<value>
```

Examples:

Top-of-house capital:

```text
/navigator/demo-suite-001?scope=toh&mode=capital&framework=Binding&window=prior_run&columns=movement
```

Desk capital:

```text
/navigator/demo-suite-001?scope=desk-rates-credit-demo&mode=desk&desk=rates-credit-demo&framework=IMA&columns=evidence
```

RFET/NMRF:

```text
/navigator/demo-suite-001?scope=business-line-rates&mode=rfet_nmrf&riskFactor=rf-girr-usd-5y&grid=rfet_register
```

PLA desk eligibility:

```text
/navigator/demo-suite-001?scope=division-ficc&mode=pla&desk=rates-credit-demo&grid=eligibility&filter=eligibility:in:amber,red
```

Pivot:

```text
/navigator/demo-suite-001?scope=le-demo&mode=pivot&rows=hierarchy,component&cols=scenario&filter=status:eq:warning&sort=movement:desc
```

AI explanation:

```text
/navigator/demo-suite-001?scope=book-credit-fixture&mode=capital&row=sa-drc-corporate&tab=explanation&explanation=exp-20260701-001
```

An `explanation` parameter is valid only if the explanation's
`inputSnapshotHash` still matches the current state-derived snapshot.

## 6. Default State

Initial load should use:

```text
runId: latest visible run or explicit route run
baselineRunId: null
hierarchyNodeId: toh
analysisMode: capital
framework: Binding
scenario: Binding
timeWindow: current
gridMode: capital_stack
rowId: first valid grid row
deskId: null
riskFactorId: null
artifactId: null
inspectorTab: summary
explanationId: null
pivotRows: []
pivotColumns: []
filters: []
hierarchySearch: ""
gridSearch: ""
sort: mode default
columnPreset: capital
artifactPage: null
```

If URL state is invalid:

- preserve valid parts;
- drop invalid selections;
- select the first valid row/object after data load;
- show a non-blocking diagnostic that the shared link was partially restored.

## 7. Reset Rules

| Change | Preserve | Reset | Notes |
| --- | --- | --- | --- |
| `runId` | `analysisMode`, `framework` if valid | baseline, row, desk, risk factor, artifact, inspector tab, explanation | Reload metadata and all result data. |
| `baselineRunId` | scope, mode, framework, selected object if still valid | explanation if snapshot hash changes | Recompute movement and driver columns. |
| `hierarchyNodeId` | mode, framework, scenario if valid | row, artifact, inspector tab, explanation | Select first valid row/object in new scope. |
| `analysisMode` | run, baseline, scope | row, desk/risk factor if incompatible, artifact, inspector tab, explanation | Switch grid and query family. |
| `framework` | run, baseline, scope, mode | row, artifact, inspector tab, explanation | Set `scenario=Binding` when framework is not `SA`. |
| `scenario` | row if still present | artifact, explanation | Applies to SBM/SA scenario-sensitive rows. |
| `timeWindow` | selected object if still present | explanation | Recompute movement/outlier/time-series panels. |
| `gridMode` | scope/mode/framework | row, artifact, inspector tab, explanation | Select first valid row in new grid. |
| `rowId` | run/scope/mode | inspector tab, artifact page, explanation | Selects inspector primary object. |
| `deskId` | run/scope/mode | row/risk factor if incompatible, explanation | Desk detail may set `hierarchyNodeId` to desk node. |
| `riskFactorId` | run/scope/mode | row/desk if incompatible, explanation | Risk factor detail keeps canonical ID. |
| `pivotRows` / `pivotColumns` / `filters` | selected object only if still present | row if absent, artifact, explanation | Refresh grid and totals. |
| `sort` | selected object if still present | none | Sorting must not change semantic selection. |
| `columnPreset` | selected object | none | Pure display unless preset changes query projection. |
| `inspectorTab` | selected object | none | If tab unavailable, fall back to summary. |
| `artifactPage` | artifact if still valid | none | Page state resets when selected object changes. |
| `explanationId` | none | none | Read-only pointer; validity checked by snapshot hash. |

Invariant: an inspector or explanation must never show evidence for a row,
desk, risk factor, artifact, scenario, hierarchy node, or run that is no longer
selected.

## 8. State-to-Query Mapping

The frontend should not query raw data directly. It should call a dashboard
adapter or result-store API with explicit state-derived parameters.

Overview:

```text
runId
baselineRunId
hierarchyNodeId
analysisMode
framework
timeWindow
```

Grid:

```text
runId
baselineRunId
hierarchyNodeId
analysisMode
framework
scenario
timeWindow
gridMode
pivotRows
pivotColumns
filters
sort
columnPreset
limit/offset where server-paged
```

Inspector:

```text
runId
baselineRunId
hierarchyNodeId
analysisMode
framework
scenario
timeWindow
rowId | deskId | riskFactorId | artifactId
inspectorTab
```

Artifact page:

```text
runId
artifactId
columns
filters
limit
offset
```

Explanation snapshot:

```text
runId
baselineRunId
hierarchyNodeId
analysisMode
framework
scenario
timeWindow
gridMode
rowId | deskId | riskFactorId | artifactId
pivotRows
pivotColumns
filters
sort
columnPreset
visible aggregate row IDs
visible diagnostic IDs
bounded source-row sample parameters
```

## 9. Cache Keys

Cache keys must include every state field that can change the response.

Format:

```text
<resource>:<stable-json-hash-of-query>
```

Resource families:

| Resource | Required key fields |
| --- | --- |
| `runs` | user entitlement context, environment |
| `metadata` | `runId` |
| `overview` | `runId`, `baselineRunId`, `hierarchyNodeId`, `analysisMode`, `framework`, `timeWindow` |
| `grid` | `runId`, `baselineRunId`, `hierarchyNodeId`, `analysisMode`, `framework`, `scenario`, `timeWindow`, `gridMode`, `pivotRows`, `pivotColumns`, `filters`, `sort`, `columnPreset`, page |
| `inspector` | `runId`, `baselineRunId`, `hierarchyNodeId`, `analysisMode`, `framework`, `scenario`, `timeWindow`, selected object, `inspectorTab` |
| `artifactPage` | `runId`, `artifactId`, `columns`, `filters`, `limit`, `offset` |
| `explanationSnapshot` | all snapshot query fields plus visible row IDs |
| `explanationResult` | `explanationId`, `inputSnapshotHash` |

Do not reuse a cache entry if:

- the run changed;
- baseline changed;
- hierarchy scope changed;
- scenario changed for scenario-sensitive data;
- selected row/object changed;
- filters or pivots changed;
- the explanation snapshot hash no longer matches.

## 10. Loading and Cancellation

Each query family needs an independent loading state:

```text
run
metadata
overview
grid
inspector
artifactPage
explanationSnapshot
explanationResult
```

Rules:

- Abort in-flight requests when their query key becomes obsolete.
- Ignore stale responses even if abort is not honoured by the transport.
- Preserve the old grid while a same-mode refresh is pending, but mark it
  refreshing.
- Clear inspector content immediately when selected object changes and no cached
  matching inspector exists.
- Keep layout stable during loading; use row skeletons or stale markers instead
  of resizing panels.
- Errors must be attached to the resource that failed, not a global ambiguous
  banner unless the whole app cannot load.

## 11. Browser Persistence

Local storage may store:

- hierarchy rail collapsed/expanded state and width;
- last selected `analysisMode`;
- last selected `framework`;
- last selected `timeWindow`;
- column presets;
- density preference;
- pinned/favourite hierarchy scopes.

Local storage must not store:

- authoritative run data;
- source rows;
- artifact pages;
- explanation snapshots;
- entitlements or hidden fields;
- secrets or API keys.

Stored preferences must be versioned:

```text
frtbNavigator.preferences.v1
```

If preference parsing fails, discard preferences and continue with defaults.

## 12. Result-Store Adapter Notes

Current demo endpoints use:

```text
/api/runs/{run_id}
/api/runs/{run_id}/metadata
/api/runs/{run_id}/grid
/api/runs/{run_id}/inspector
```

Target production data should come from `frtb-result-store` surfaces described
in `RESULT_STORE_DATA_CONTRACT.md`. Until then, the dashboard adapter should
present stable view models that are compatible with this state contract.

Adapter requirements:

- Accept `NavigatorState`-derived query parameters explicitly.
- Return no-data states explicitly rather than forcing the UI to infer them.
- Preserve result-store IDs in every response.
- Provide row selection fallbacks: first valid row, first warning row, or no-row
  with reason.
- Include a response key or snapshot hash when data is suitable for explanation
  or export.

## 13. Test Expectations

When implementing this state contract, tests should cover:

- URL parsing and serialization round trips.
- Default state creation.
- Reset rules for run, baseline, scope, framework, scenario, mode, row, desk,
  risk factor, pivot, and filters.
- Cache-key changes for every query-affecting state field.
- Stale inspector prevention after scope, row, scenario, and mode changes.
- Explanation invalidation when `inputSnapshotHash` changes.
- Local-storage preference migration and parse failure.
- Aborted/stale request handling.
- Shared-link recovery when some referenced state is invalid.

## 14. Implementation Non-Goals

- Do not implement a full state-management library just to satisfy this spec.
- Do not choose final router technology here.
- Do not duplicate result-store schemas.
- Do not store source rows or explanations in local storage.
- Do not let browser-computed grouping become an official subtotal.

