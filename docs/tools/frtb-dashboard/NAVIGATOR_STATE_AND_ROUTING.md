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
and state-to-query mapping. It does not define result-store response schemas.
Use the existing `frtb-result-store` public API and storage-contract documents
for persisted evidence contracts; the dashboard adapter must expose stable view
models that are compatible with this state contract.

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
  analysisMode: capital | hierarchy | desk | pla | rfet_nmrf | risk_factor | pivot
  framework: SA | IMA | CVA
  capitalView: binding | framework
  scenario: Binding | Base | High | Low
  timeWindow: current | prior_run | prior_business_day | month_end | quarter_end | year_on_year | custom
  customWindow: CustomWindowSpec | null
  gridMode: capital_stack | drivers | evidence | source_rows | eligibility | rfet_register | time_series | pivot
  rowId: string | null
  deskId: string | null
  riskFactorId: string | null
  artifactId: string | null
  selectedDrilldownTarget: DrilldownTarget | null
  inspectorTab: summary | attribution | source | model | diagnostics | lineage | explanation
  explanationId: string | null
  pivotRows: string[]
  pivotColumns: string[]
  filters: FilterSpec[]
  hierarchySearch: string
  gridSearch: string
  sort: SortSpec[]
  columnPreset: capital | movement | evidence | source | compact
  columnLayout: ColumnLayoutSpec | null
  artifactPage: PageSpec | null
```

Supporting shapes:

```text
FilterSpec
  field: string
  op: eq | in | contains | range
  value: string | number | boolean | string[] | number[]

SortSpec
  field: string
  direction: asc | desc

PageSpec
  limit: number
  offset: number
  columns: string[]
  filters: FilterSpec[]

ColumnLayoutSpec
  visibleColumns: string[]
  columnWidths: map<string, number>
  pinnedColumns: string[]

CustomWindowSpec
  start: ISO date | run alias | run id
  end: ISO date | run alias | run id
  basis: business_date | run_id

DrilldownTarget
  bindingSource: SA | IMA | CVA | output_floor | null
  framework: SA | IMA | CVA | null
  rowId: string | null
  component: string | null
  artifactId: string | null
```

## 4. State Ownership

| State | URL | Server query | Local storage | Ephemeral only |
| --- | --- | --- | --- | --- |
| `runId` | yes | yes | no | no |
| `baselineRunId` | yes | yes | no | no |
| `hierarchyNodeId` | yes | yes | no | no |
| `analysisMode` | yes | yes | no | no |
| `framework` | yes | yes | no | no |
| `capitalView` | yes | yes | no | no |
| `scenario` | yes | yes | no | no |
| `timeWindow` | yes | yes | no | no |
| `customWindow` | yes when `timeWindow=custom` | yes when `timeWindow=custom` | no | no |
| `gridMode` | yes | yes | no | no |
| `rowId` | yes | yes for inspector | no | no |
| `deskId` | yes | yes | no | no |
| `riskFactorId` | yes | yes | no | no |
| `artifactId` | yes | yes | no | no |
| `selectedDrilldownTarget` | no, derived from selected row | yes for evidence queries when present | no | no |
| `artifactPage` | yes when artifact/source tab is open | yes | no | no |
| `inspectorTab` | yes | no | no | no |
| `explanationId` | yes, if snapshot-valid | yes | no | no |
| `pivotRows` | yes | yes | no | no |
| `pivotColumns` | yes | yes | no | no |
| `filters` | yes | yes | no | no |
| `hierarchySearch` | no | no | no | yes |
| `gridSearch` | yes when server-side, no when local-only | yes when server-side | no | no |
| `sort` | yes | yes | no | no |
| `columnPreset` | yes | yes | no | no |
| `columnLayout` | no | no | yes | no |
| hierarchy rail collapsed/width | no | no | yes | no |
| loading/error/abort controllers | no | no | no | yes |

Rules:

- URL state must be enough to restore the analytical view.
- Local storage may improve ergonomics, but it must not change query semantics
  silently.
- Ephemeral state must never be required to reproduce a finding.
- State precedence for analytical state is strict:
  1. explicit URL state;
  2. route defaults, such as `runId` from `/navigator/:runId`;
  3. product defaults.
- Local preferences must never set analytical state on `/navigator/:runId`.
  They may set only ergonomic display state, such as rail width, collapsed state,
  density, and pinned scopes.
- A non-shareable landing route, such as `/navigator`, may use local preferences
  to choose a recent run or scope before redirecting to a URL that explicitly
  serializes the selected run, scope, mode, and other analytical state.
- Search ownership must be explicit per grid mode. Client-side search is a local
  convenience and is excluded from share links, exports, and explanation
  snapshots. Server-side search changes the result set and must be represented
  in URL state, cache keys, exports, and explanation snapshots.

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
| `view` | `capitalView` | `binding` |
| `framework` | `framework` | `SA` |
| `scenario` | `scenario` | `High` |
| `window` | `timeWindow` | `month_end` |
| `from` | `customWindow.start`, when `window=custom` | `2026-06-01` |
| `to` | `customWindow.end`, when `window=custom` | `2026-06-30` |
| `windowBasis` | `customWindow.basis`, when `window=custom` | `business_date` |
| `grid` | `gridMode` | `drivers` |
| `row` | `rowId` | `sa-drc-corporate` |
| `desk` | `deskId` | `rates-credit-demo` |
| `riskFactor` | `riskFactorId` | `rf-girr-usd-5y` |
| `artifact` | `artifactId` | `artifact-id` |
| `artifactLimit` | `artifactPage.limit` | `100` |
| `artifactOffset` | `artifactPage.offset` | `200` |
| `artifactCols` | `artifactPage.columns` | `trade_id,amount` |
| `artifactFilter` | `artifactPage.filters`, repeated | `book:eq:rates` |
| `tab` | `inspectorTab` | `source` |
| `explanation` | `explanationId` | `exp-123` |
| `rows` | `pivotRows` | `hierarchy,component` |
| `cols` | `pivotColumns` | `scenario` |
| `filter` | repeated filter specs | `component:eq:SBM` |
| `sort` | sort specs | `movement:desc` |
| `search` | `gridSearch`, only for server-side search | `issuer123` |
| `columns` | `columnPreset` | `movement` |

Filter and sort syntax in URLs should stay simple and consistent. Query
parameters are percent-decoded once before parsing; literal `:` and `,` inside
values must be percent-encoded by the serializer. Range bounds cannot contain
the reserved `..` separator.

```text
filter=<field>:<op>:<value>
artifactFilter=<field>:<op>:<value>
sort=<field>:<direction>
```

Grammar:

```text
field      = ALPHA / DIGIT / "_" / "-" / "." repeated
op         = "eq" | "in" | "contains" | "range"
direction  = "asc" | "desc"
eq         = filter=component:eq:SBM
in         = filter=eligibility:in:amber,red
range      = filter=amount:range:100..250
multi-sort = sort=movement:desc&sort=capital:desc
```

Rules:

- Repeated `filter` parameters are combined with `AND`.
- Repeated `artifactFilter` parameters use the same grammar and apply only to
  the active artifact/source page, after the inherited analytical scope.
- `in` values are comma-separated after URL decoding; literal commas in values
  must be encoded as `%2C`.
- `range` values use `lower..upper`; open bounds are allowed as `..250` or
  `100..`.
- Multi-column sort uses repeated `sort` parameters in priority order.
- The canonical serializer sorts filters by field, operator, and value, but
  preserves sort priority order.

Syntax examples:

```text
filter=component:eq:SBM
filter=eligibility:in:amber,red
filter=amount:range:100..250
sort=movement:desc&sort=capital:desc
```

Examples:

Top-of-house capital:

```text
/navigator/demo-suite-001?scope=toh&mode=capital&view=binding&framework=SA&window=prior_run&columns=movement
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

Custom window:

```text
/navigator/demo-suite-001?scope=toh&mode=capital&window=custom&from=2026-06-01&to=2026-06-30&windowBasis=business_date
```

AI explanation:

```text
/navigator/demo-suite-001?scope=book-credit-fixture&mode=capital&row=sa-drc-corporate&tab=explanation&explanation=exp-20260701-001
```

An `explanation` parameter is valid only if the explanation's
`inputSnapshotHash` still matches the current state-derived snapshot.

## 6. State Normalization

`analysisMode`, `capitalView`, and `framework` have different jobs:

- `analysisMode` selects the analytical workflow and screen shape.
- `capitalView` selects whether the capital strip and top-level grid emphasise
  binding capital or a specific framework.
- `framework` selects the framework-specific data family accepted by backend and
  result-store adapters: `SA`, `IMA`, or `CVA`.

Compatibility:

| `analysisMode` | Valid `capitalView` | Valid `framework` | Normalization |
| --- | --- | --- | --- |
| `capital` | `binding`, `framework` | `SA`, `IMA`, `CVA` | `view=binding` may still query SA/IMA/CVA summaries. |
| `hierarchy` | `binding`, `framework` | `SA`, `IMA`, `CVA` | Preserve framework for component filtering. |
| `desk` | `binding`, `framework` | `SA`, `IMA`, `CVA` | Preserve framework if desk has matching data; otherwise fallback to `SA`. |
| `pla` | `framework` | `IMA` | Force `framework=IMA`, `scenario=Binding`. |
| `rfet_nmrf` | `framework` | `IMA` | Force `framework=IMA`, `scenario=Binding`. |
| `risk_factor` | `framework` | `SA`, `IMA` | Preserve `SA` or `IMA`; reject/normalize `CVA` to `IMA`. |
| `pivot` | `binding`, `framework` | `SA`, `IMA`, `CVA` | Pivot dimensions determine which framework rows are returned. |

Normalization rules:

- Never serialize `framework=Binding`; binding is represented by `view=binding`.
- If URL state contains an invalid combination, preserve the route but normalize
  to the closest valid state and emit a `link_restore_warning` diagnostic.
- If a mode forces `framework=IMA`, also force `scenario=Binding`.
- If `framework` is not `SA`, force `scenario=Binding`.
- If `capitalView=framework`, the selected framework controls the capital strip
  emphasis and grid data family.
- If `capitalView=binding`, top-level rows must carry a resolved
  `bindingSource` and `DrilldownTarget`. Do not use the ambient `framework`
  alone to open a binding row, because binding capital may be IMA, SA, CVA, or
  output-floor driven.
- The ambient `framework` in binding view is only a framework filter/default for
  framework-specific rows that do not carry their own `DrilldownTarget`.
- `selectedDrilldownTarget` is derived from the currently selected grid row. It
  is never serialized into the URL. If the selected row ID is restored before
  grid data has loaded, the inspector must wait for the grid response to resolve
  the target or show a pending/no-data state; it must not infer a framework from
  ambient state.
- If `timeWindow=custom`, `customWindow` is required and must include `start`,
  `end`, and `basis`. If any part is invalid, normalize to `current`, clear
  `customWindow`, and emit `link_restore_warning`.
- If `timeWindow` is not `custom`, `customWindow` must be `null` and omitted
  from serialized URLs.

## 7. Default State

Initial load should use:

```text
runId: latest visible run or explicit route run
baselineRunId: null
hierarchyNodeId: toh
analysisMode: capital
framework: SA
capitalView: binding
scenario: Binding
timeWindow: current
customWindow: null
gridMode: capital_stack
rowId: first valid grid row
deskId: null
riskFactorId: null
artifactId: null
selectedDrilldownTarget: null
inspectorTab: summary
explanationId: null
pivotRows: []
pivotColumns: []
filters: []
hierarchySearch: ""
gridSearch: ""
sort: mode default
columnPreset: capital
columnLayout: null
artifactPage: null
```

If URL state is invalid:

- preserve valid parts;
- drop invalid selections;
- select the first valid row/object after data load;
- show a non-blocking diagnostic that the shared link was partially restored.

The app should expose any URL normalization or partial restoration as a
diagnostic:

```text
Diagnostic
  code: link_restore_warning
  severity: info | warning
  message
  originalParameter
  normalizedValue
```

This diagnostic belongs in the header/context diagnostics and in the inspector
limitations if an explanation is generated from the restored view.

## 8. Reset Rules

| Change | Preserve | Reset | Notes |
| --- | --- | --- | --- |
| `runId` | `analysisMode`, `capitalView`, `framework` if valid | baseline, row, desk, risk factor, artifact, inspector tab, explanation | Reload metadata and all result data. |
| `baselineRunId` | scope, mode, view, framework, selected object if still valid | explanation if snapshot hash changes | Recompute movement and driver columns. |
| `hierarchyNodeId` | mode, view, framework, scenario if valid | row, artifact, inspector tab, explanation | Select first valid row/object in new scope. |
| `analysisMode` | run, baseline, scope | row, desk/risk factor if incompatible, artifact, inspector tab, explanation | Switch grid and query family. |
| `capitalView` | run, baseline, scope, mode, framework | row if no longer present, explanation | Changes top-level capital emphasis. |
| `framework` | run, baseline, scope, mode | row, artifact, inspector tab, explanation | Set `scenario=Binding` when framework is not `SA`. |
| `scenario` | row if still present | artifact, explanation | Applies to SBM/SA scenario-sensitive rows. |
| `timeWindow` / `customWindow` | selected object if still present | explanation | Recompute movement/outlier/time-series panels; `customWindow` is valid only with `timeWindow=custom`. |
| `gridMode` | scope/mode/framework | row, artifact, inspector tab, explanation | Select first valid row in new grid. |
| `rowId` | run/scope/mode | selected drilldown target, inspector tab, artifact page, explanation | Selects inspector primary object; target is re-derived from refreshed grid row. |
| `deskId` | run/scope/mode | row/risk factor if incompatible, explanation | Desk detail may set `hierarchyNodeId` to desk node. |
| `riskFactorId` | run/scope/mode | row/desk if incompatible, explanation | Risk factor detail keeps canonical ID. |
| `pivotRows` / `pivotColumns` / `filters` | selected object only if still present | row if absent, artifact, explanation | Refresh grid and totals. |
| `sort` | selected object if still present | none | Sorting must not change semantic selection. |
| `columnPreset` | selected object | none | Query-affecting server projection preset. |
| `columnLayout` | selected object | none | Local display preference only; never changes server projection. |
| `inspectorTab` | selected object | none | If tab unavailable, fall back to summary. |
| `artifactPage` | artifact if still valid | none | Page state resets when selected object changes. |
| `explanationId` | none | none | Read-only pointer; validity checked by snapshot hash. |

Invariant: an inspector or explanation must never show evidence for a row,
desk, risk factor, artifact, scenario, hierarchy node, or run that is no longer
selected.

## 9. State-to-Query Mapping

The frontend should not query raw data directly. It should call a dashboard
adapter or result-store API with explicit state-derived parameters.

Overview:

```text
runId
baselineRunId
hierarchyNodeId
analysisMode
framework
capitalView
timeWindow
customWindow if timeWindow=custom
```

Grid:

```text
runId
baselineRunId
hierarchyNodeId
analysisMode
framework
capitalView
scenario
timeWindow
customWindow if timeWindow=custom
gridMode
pivotRows
pivotColumns
filters
gridSearch if server-side
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
capitalView
scenario
timeWindow
customWindow if timeWindow=custom
rowId | deskId | riskFactorId | artifactId
selectedDrilldownTarget when selected row provides one
inspectorTab
```

Inspector requests for binding-view rows must use `selectedDrilldownTarget` when
present. If the selected row carries a drilldown target and that target has not
been resolved yet, defer the inspector request until the matching grid response
arrives. If the target resolves to `bindingSource=output_floor`, show the output
floor explanation/evidence panel instead of forcing an SA, IMA, or CVA
framework query.

Artifact page:

```text
runId
baselineRunId
hierarchyNodeId
analysisMode
framework
capitalView
scenario
timeWindow
customWindow if timeWindow=custom
gridMode
rowId | deskId | riskFactorId
selectedDrilldownTarget when selected row provides one
artifactId
artifactPage.columns
state filters
artifactPage.filters
gridSearch if server-side
artifactPage.limit
artifactPage.offset
```

Artifact and source-row pages must inherit the analytical scope that produced
the selected row. An `artifactId` alone is not enough unless the adapter
contract explicitly declares the artifact immutable and already scoped to the
selected run, hierarchy node, framework, scenario, mode, filters, and selected
object. If that declaration is absent, the adapter must pass the full
state-derived scope above and return a no-data or mismatch diagnostic instead
of showing rows from a broader artifact.

When `artifactPage` is not null, `artifactId` is the canonical selected artifact
identifier. `artifactPage` owns only paging, projection, and artifact-local
filters for that artifact; it must not carry a second artifact identifier.

Explanation snapshot:

```text
runId
baselineRunId
hierarchyNodeId
analysisMode
framework
capitalView
scenario
timeWindow
customWindow if timeWindow=custom
gridMode
rowId | deskId | riskFactorId | artifactId
selectedDrilldownTarget when selected row provides one
pivotRows
pivotColumns
filters
gridSearch if server-side
sort
columnPreset
visible aggregate row IDs
visible diagnostic IDs
bounded source-row sample parameters
```

## 10. Cache Keys

Cache keys must include every state field that can change the response and must
be isolated by user/session entitlement context in production deployments.

Format:

```text
<resource>:<stable-json-hash-of-query>
```

Resource families:

| Resource | Required key fields |
| --- | --- |
| `runs` | environment, entitlement context |
| `metadata` | environment, entitlement context, `runId` |
| `overview` | environment, entitlement context, `runId`, `baselineRunId`, `hierarchyNodeId`, `analysisMode`, `capitalView`, `framework`, `timeWindow`, `customWindow` when custom |
| `grid` | environment, entitlement context, `runId`, `baselineRunId`, `hierarchyNodeId`, `analysisMode`, `capitalView`, `framework`, `scenario`, `timeWindow`, `customWindow` when custom, `gridMode`, `pivotRows`, `pivotColumns`, `filters`, server-side `gridSearch`, `sort`, `columnPreset`, page |
| `inspector` | environment, entitlement context, `runId`, `baselineRunId`, `hierarchyNodeId`, `analysisMode`, `capitalView`, `framework`, `scenario`, `timeWindow`, `customWindow` when custom, selected object, `selectedDrilldownTarget` when present, `inspectorTab` |
| `artifactPage` | environment, entitlement context, `runId`, `baselineRunId`, `hierarchyNodeId`, `analysisMode`, `capitalView`, `framework`, `scenario`, `timeWindow`, `customWindow` when custom, `gridMode`, selected object, `selectedDrilldownTarget` when present, `artifactId`, `columns`, page filters, state filters, server-side `gridSearch`, `limit`, `offset` |
| `explanationSnapshot` | environment, entitlement context, all snapshot query fields, `selectedDrilldownTarget` when present, plus visible row IDs |
| `explanationResult` | environment, entitlement context, `explanationId`, `inputSnapshotHash` |

Do not reuse a cache entry if:

- the run changed;
- baseline changed;
- hierarchy scope changed;
- capital view changed;
- scenario changed for scenario-sensitive data;
- custom-window start, end, or basis changed;
- selected row/object changed;
- filters or pivots changed;
- server-side search changed;
- the explanation snapshot hash no longer matches.

## 11. Loading and Cancellation

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

## 12. Browser Persistence

Local storage may store:

- hierarchy rail collapsed/expanded state and width;
- density preference;
- `columnLayout` display preferences that do not change server projection or
  aggregate content;
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

Preference application order:

- Build analytical state from product defaults, then route and URL state.
- Normalize analytical state without consulting local preferences.
- Apply local preferences only to ergonomic display state after data-query state
  is resolved.
- Emit `link_restore_warning` diagnostics for discarded or normalized URL
  values.
- Never emit warnings for ignored local preferences, because local preferences
  must not be allowed to change analytical state.

## 13. Result-Store Adapter Notes

Current demo endpoints use:

```text
/api/runs/{run_id}
/api/runs/{run_id}/metadata
/api/runs/{run_id}/grid
/api/runs/{run_id}/inspector
```

Target production data should come from `frtb-result-store` surfaces documented
in `docs/modules/frtb-result-store/PUBLIC_API.md` and
`docs/modules/frtb-result-store/STORAGE_CONTRACT.md`. The dashboard adapter
should present stable view models that are compatible with this state contract.

Adapter requirements:

- Accept `NavigatorState`-derived query parameters explicitly.
- Return no-data states explicitly rather than forcing the UI to infer them.
- Preserve result-store IDs in every response.
- Provide row selection fallbacks: first valid row, first warning row, or no-row
  with reason.
- Include a response key or snapshot hash when data is suitable for explanation
  or export.

## 14. Test Expectations

When implementing this state contract, tests should cover:

- URL parsing and serialization round trips.
- Default state creation.
- State normalization and compatibility matrix cases.
- Binding-view row selection through resolved `DrilldownTarget`, including
  output-floor-driven binding rows.
- Deferred inspector requests while a restored selected row is waiting for its
  server-resolved `selectedDrilldownTarget`.
- Artifact/source pages and explanation snapshots include
  `selectedDrilldownTarget` when present.
- `window=custom` parsing, serialization, invalid-window diagnostics, and cache
  invalidation.
- Reset rules for run, baseline, scope, framework, scenario, mode, row, desk,
  risk factor, pivot, and filters.
- URL/filter/sort grammar, including repeated filters, repeated sorts, range
  filters, and percent-encoded reserved characters.
- URL/local-storage precedence, including proof that local preferences cannot
  change analytical state for `/navigator/:runId`.
- Cache-key changes for every query-affecting state field.
- Entitlement/environment isolation in cache keys.
- Client-side versus server-side search behavior.
- Artifact/source-row paging inherits run, baseline, scope, framework, scenario,
  mode, filters, and selected object.
- `artifactId` remains the single selected artifact identifier; `artifactPage`
  carries only paging, projection, and artifact-local filters.
- Stale inspector prevention after scope, row, scenario, and mode changes.
- Explanation invalidation when `inputSnapshotHash` changes.
- Local-storage preference migration and parse failure.
- Aborted/stale request handling.
- Shared-link recovery when some referenced state is invalid.

## 15. Implementation Non-Goals

- Do not implement a full state-management library just to satisfy this spec.
- Do not choose final router technology here.
- Do not duplicate result-store schemas.
- Do not store source rows or explanations in local storage.
- Do not let browser-computed grouping become an official subtotal.
