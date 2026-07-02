# FRTB Navigator mode wireframes

Status: draft implementation contract for issue #1110.

Audience: FRTB Navigator frontend/backend implementers, result-store adapter
authors, product reviewers, and market-risk stakeholders validating screen
anatomy before implementation.

Related:

- UX contract:
  [`UX_AUDIT_AND_INTERACTION_CONTRACT.md`](UX_AUDIT_AND_INTERACTION_CONTRACT.md)
- State and routing contract:
  [`NAVIGATOR_STATE_AND_ROUTING.md`](NAVIGATOR_STATE_AND_ROUTING.md)
- Capital and movement semantics:
  [`CAPITAL_AND_MOVEMENT_SEMANTICS.md`](CAPITAL_AND_MOVEMENT_SEMANTICS.md)
- Implementation slices:
  [`IMPLEMENTATION_SLICES.md`](IMPLEMENTATION_SLICES.md)
- AI explanation contract:
  [`AI_EXPLANATION_CONTRACT.md`](AI_EXPLANATION_CONTRACT.md)
- Result-store data contract:
  [`RESULT_STORE_DATA_CONTRACT.md`](RESULT_STORE_DATA_CONTRACT.md)

This document defines low-fidelity, buildable screen anatomy for the Capital
Navigator shell and major analytical modes. It is not a visual design comp. It
does not define final colours, type scale, CSS, React components, or detailed
copy.

## Wireframe Principles

The Navigator is one analytical workbench. Mode changes replace the primary
grid and inspector emphasis, but they do not replace the shell.

Rules:

- Keep one selected run, scope, baseline, mode, row/object, and evidence target
  visible at all times.
- Keep the selected hierarchy path visible in the header breadcrumb even when
  the hierarchy rail is compact or hidden.
- Keep AI explanation as commentary beside evidence. It must never replace the
  grid, inspector, source rows, diagnostics, or lineage.
- Keep every mode on one screen: header, capital strip, one primary grid or
  matrix, inspector, and optional AI drawer.
- Hide raw rows, advanced pivots, column layout, JSON, and long evidence lists
  until the user asks for them.
- Label unavailable, unsupported, stale, synthetic, partial, no-data, and
  display-only states where the user would otherwise infer a false zero or
  official subtotal.

## Product Mode to NavigatorState Mapping

Wireframe section names are product labels, not additional route keys. The
canonical route/state contract remains `NavigatorState` in
[`NAVIGATOR_STATE_AND_ROUTING.md`](NAVIGATOR_STATE_AND_ROUTING.md).

| Product surface | Canonical `analysisMode` | Required state pattern |
| --- | --- | --- |
| Top-of-house capital | `capital` | `hierarchyNodeId=toh`, `capitalView=binding`, `gridMode=capital_stack`; framework chips may set `framework=SA|IMA|CVA` for focused rows. |
| Legal entity and business capital | `hierarchy` | Selected `hierarchyNodeId`, `capitalView=binding|framework`, `gridMode=capital_stack` or `drivers`; inline expansion is display state unless it changes selected scope. |
| Desk and book capital | `desk` | Desk/book `hierarchyNodeId`, `deskId` where available, `framework=SA|IMA|CVA`, `gridMode=capital_stack|drivers|evidence|source_rows`. |
| Standardised Approach capital | `capital` | `capitalView=framework`, `framework=SA`, `scenario=Binding|Base|High|Low`, `gridMode=capital_stack|drivers|evidence|source_rows`. |
| IMA capital and model evidence | `capital` or `desk` | `framework=IMA`; use `analysisMode=capital` for scope-level IMA rows and `analysisMode=desk` when desk/book selection is primary; evidence detail uses `gridMode=evidence`. |
| CVA capital | `capital` | `capitalView=framework`, `framework=CVA`, `gridMode=capital_stack|evidence|source_rows`; no-data and unsupported states are row/view state, not separate routes. |
| Desk eligibility and PLA | `pla` | Force `framework=IMA`, `scenario=Binding`, `gridMode=eligibility`, and set `deskId` when a desk is selected. |
| RFET, NMRF, and SES | `rfet_nmrf` | Force `framework=IMA`, `scenario=Binding`, `gridMode=rfet_register|evidence`, and preserve `riskFactorId` when selected. |
| Risk-factor and time-series drivers | `risk_factor` | `framework=SA|IMA`, `gridMode=drivers|time_series`, selected `riskFactorId`, and active `timeWindow`. |
| Interactive pivot and hierarchy analysis | `pivot` | `gridMode=pivot`, `pivotRows`, `pivotColumns`, `filters`, `sort`, and selected subtotal row. |
| AI explanation overlay | current mode retained | Not a distinct `analysisMode`; set `inspectorTab=explanation` and `explanationId` on the current run/scope/mode snapshot. |

Inspector labels in the wireframes are display labels. They must map back to
the canonical `inspectorTab` values:
`summary | attribution | source | model | diagnostics | lineage | explanation`.
Mode-specific labels such as `Component mix`, `Usage map`, `SES bridge`,
`Hedge evidence`, or `Time series` are sub-panels under those canonical tabs,
not new `inspectorTab` enum values.

## Stable Shell

Expanded hierarchy rail:

```text
+----------------------------------------------------------------------------+
| Run 2026-06-30 | baseline prior run | Top / LE-DEMO / FICC / Rates | status |
+----------------+-----------------------------------------------------------+
| Hierarchy      | Binding 120 +5 | IMA 120 +4 | SA 150 +8 | Floor 108 | CVA |
| search         +-----------------------------------------------------------+
| > Top          | Mode tabs | framework | scenario | filters | Explain view |
|   > LE-DEMO    +------------------------------------+----------------------+
|     > FICC     | Primary grid or matrix             | Inspector            |
|       > Rates  | sticky label | current | move | ...| Summary              |
|         Book A | row 1        |         |      |    | Attribution/Capital  |
|         Book B | row 2        |         |      |    | Source rows          |
| badges         | row 3        |         |      |    | Model evidence       |
|                | row 4        |         |      |    | Diagnostics          |
|                | page/sort/status                   | Lineage              |
+----------------+------------------------------------+----------------------+
```

Compact hierarchy rail with AI drawer open:

```text
+----------------------------------------------------------------------------+
| Run | baseline | Top / LE-DEMO / FICC / Rates / Book A | status | user     |
+----+-----------------------------------------------------------------------+
| [] | Binding | IMA | SA | Floor | CVA | movement | data quality            |
| [] +----------------------------------+------------------+-----------------+
| [] | Grid controls and filter chips   | Inspector        | AI explanation  |
| [] +----------------------------------+------------------+-----------------+
| [] | Primary grid                     | Evidence tabs    | Findings        |
| [] | selected row remains visible     | Source/lineage   | Evidence chips  |
| [] |                                  | Diagnostics      | Limitations     |
+----+----------------------------------+------------------+-----------------+
```

Hidden hierarchy rail on narrow screens:

```text
+----------------------------------------------------------------+
| Run | Top / LE-DEMO / FICC / Rates / Book A | menu | status    |
+----------------------------------------------------------------+
| Binding | IMA | SA | Floor | CVA | movement                     |
+----------------------------------------------------------------+
| Mode | filters | Explain                                         |
+----------------------------------------------------------------+
| Primary grid or selected-row stack                              |
+----------------------------------------------------------------+
| Inspector drawer opens over lower portion; AI opens as tab       |
+----------------------------------------------------------------+
```

Shared regions:

| Region | Required content | Notes |
| --- | --- | --- |
| Header | run, baseline, breadcrumb scope, date/profile, data state | Breadcrumb remains visible when rail collapses. |
| Hierarchy rail | enterprise/trading-book tree, search, pins, badges | Collapsing never changes selected scope. |
| Capital strip | binding, IMA, SA, floor, CVA, movement, quality | Compact strip, not large cards. |
| Grid controls | mode, framework/scenario where relevant, filters, search, explain action | Controls fit one row where possible. |
| Primary grid | one task-specific table or matrix | Row selection drives inspector. |
| Inspector | summary, attribution/capital, source, model, diagnostics, lineage | Tabs are mode-aware but predictable. |
| AI drawer | generated commentary, evidence chips, limitations, next actions | Opens beside inspector or as `inspectorTab=explanation` on compact screens. |

## Shared Responsive Behaviour

Desktop:

- Hierarchy rail can be expanded, compact, or hidden.
- Inspector is a right panel.
- AI explanation opens as a second right drawer or as an inspector-adjacent
  drawer when there is enough width.

Tablet:

- Hierarchy rail defaults to compact.
- Inspector can be pinned or overlaid.
- AI explanation opens as a tab within the inspector stack.

Phone or narrow embedded view:

- Hierarchy rail is hidden behind a menu.
- Breadcrumb remains in the header and wraps before it truncates material scope.
- Capital strip becomes a two-row compact list.
- Grid uses fewer columns and a selected-row details drawer.
- AI explanation is an inspector tab labelled by snapshot state.

## Mode: Top-of-House Capital

```text
Header: run, baseline, Top of house breadcrumb, profile, data state
Capital strip: BINDING | IMA | SA | FLOOR | CVA | movement
+----------------------------------------------+---------------------------+
| Component/business contribution grid         | Inspector: selected row   |
| component/business | current | base | move   | Summary                   |
| move % | contrib total | contrib move | stat | Attribution               |
| IMA                 |         |      |       | Source lineage            |
| SA / SBM            |         |      |       | Diagnostics               |
| SA / DRC            |         |      |       | Lineage                   |
| SA / RRAO           |         |      |       |                           |
| CVA                 |         |      |       | [Explain selected row]    |
| Legal entity rows   |         |      |       |                           |
+----------------------------------------------+---------------------------+
```

- First-read summary: binding capital, movement versus selected baseline,
  binding driver, top positive mover, top negative mover, and data quality.
- Primary grid columns: component/business, current, baseline, movement,
  movement percent, contribution to total, contribution to movement, status,
  evidence count.
- Inspector tabs: Summary, Attribution, Source lineage, Diagnostics, Lineage,
  Explanation.
- Primary actions: change baseline, switch framework, expand top mover, explain
  view, copy executive finding.
- Hidden/deferred controls: distribution, scenario comparison, raw rows, full
  hierarchy attributes, column layout.
- Responsive behaviour: compact view keeps binding, movement, and top mover
  visible; component rows become the first grid; legal-entity rows move behind a
  hierarchy filter.

## Mode: Legal Entity and Business Capital

```text
Header breadcrumb: Top / LE-DEMO / FICC
Capital strip: scoped binding | share of top | movement | warnings
+----------------+-------------------------------+--------------------------+
| Hierarchy rail | Business hierarchy grid        | Inspector: hierarchy     |
| LE-DEMO        | node | type | current | move  | Component mix            |
| > FICC         | share parent | share top | ... | Child contribution       |
|   Rates        | FICC | division |        |    | Completeness             |
|   Credit       | Rates | desk    |        |    | Top drivers              |
|   Residual     | Book A | book   |        |    | Diagnostics              |
+----------------+-------------------------------+--------------------------+
```

- First-read summary: selected hierarchy path, scoped binding capital,
  movement, percentage of top-of-house, child desk/book count, and warning
  count.
- Primary grid columns: hierarchy node, node type, current, baseline, movement,
  share of parent, share of top-of-house, child count, warning count,
  model/data state.
- Inspector tabs: Summary, Component mix, Children, Source rows, Diagnostics,
  Lineage, Explanation.
- Primary actions: expand/collapse node, filter to subtree, open child scope,
  show warnings, explain selected scope, copy scope link.
- Hidden/deferred controls: ownership metadata, entitlement detail, long IDs,
  display-only grouped totals.
- Responsive behaviour: rail can collapse to compact initials or hide; the
  header breadcrumb remains visible and the grid keeps node path as the sticky
  label column.

## Mode: Desk and Book Capital

```text
Header breadcrumb: Top / LE-DEMO / FICC / Rates / Book A
Capital strip: desk/book capital | model path | SES/NMRF | PLA | movement
+----------------------------------------------+---------------------------+
| Desk/book grid                               | Inspector: desk/book      |
| book/component/driver | current | base | move | Why this number exists    |
| model | RFET/NMRF | PLA/BT | source | stat  | Capital terms             |
| Book A / IMA         |         |      |      | Model evidence            |
| Book A / SBM         |         |      |      | Source rows               |
| Risk-factor driver   |         |      |      | Diagnostics               |
+----------------------------------------------+---------------------------+
```

- First-read summary: desk/book capital, model path, movement,
  eligibility state, SES/NMRF amount, and largest source driver.
- Primary grid columns: book/component/risk driver, current, baseline,
  movement, model state, RFET/NMRF state, PLA/backtesting state, source count,
  status.
- Inspector tabs: Summary, Capital, Model evidence, Source rows, Diagnostics,
  Lineage, Explanation.
- Primary actions: open eligibility, open RFET/NMRF, open source rows, compare
  prior run/month, explain selected desk/book.
- Hidden/deferred controls: full source-system coverage, full source timestamp
  history, book ownership metadata, raw vectors.
- Responsive behaviour: direct desk/book links open with compact rail; compact
  columns keep model path, movement, RFET/NMRF, PLA/backtesting, and status.

## Mode: Standardised Approach Capital

```text
Header breadcrumb: selected scope
Capital strip: SA total | SBM | DRC | RRAO | scenario | movement
+----------------------------------------------+---------------------------+
| SA component grid                            | Inspector: SA row         |
| component | risk class/category | bucket     | Component summary         |
| current | baseline | movement | scenario    | Attribution/capital       |
| source count | status                        | Source rows               |
| SBM / GIRR / delta                           | SBM scenario details      |
| DRC / corporate / issuer bucket              | DRC issuer evidence       |
| RRAO / residual category                     | RRAO classification       |
+----------------------------------------------+---------------------------+
```

- First-read summary: SA total, SBM/DRC/RRAO split, selected SBM scenario,
  movement, largest component mover, and unsupported/no-data component count.
- Primary grid columns: component, risk class/category, bucket, current,
  baseline, movement, scenario values where applicable, source count, status.
- Inspector tabs: Summary, Attribution/Capital, Source rows, Component
  evidence, Diagnostics, Lineage, Explanation.
- Primary actions: scenario toggle, component filter, show top movers, open
  source rows, explain selected component.
- Hidden/deferred controls: all SBM scenario columns for non-SBM rows, excluded
  RRAO rows, all DRC formula intermediates, raw CRIF/sensitivity rows.
- Responsive behaviour: scenario control collapses to a menu; component remains
  the sticky label; component-specific details move to inspector tabs.

## Mode: IMA Capital and Model Evidence

```text
Header breadcrumb: selected scope, framework IMA
Capital strip: IMA | IMCC | SES | multiplier/fallback | desk state | movement
+----------------------------------------------+---------------------------+
| IMA desk grid                                | Inspector: selected desk  |
| desk | current IMA | baseline | movement     | Eligibility and why       |
| IMCC | SES | NMRF count | PLA | BT | RFET    | IMCC / ES terms           |
| Rates desk                                   | SES/NMRF terms            |
| Credit desk                                  | PLA/backtesting           |
| Desk drilldown rows                          | RFET links                |
+----------------------------------------------+---------------------------+
```

- First-read summary: IMA capital, IMCC, SES, multiplier/fallback state,
  eligible desk count, amber/red desk count, and model-evidence freshness.
- Primary grid columns: desk, current IMA, baseline IMA, movement, IMCC, SES,
  NMRF count, PLA state, backtesting zone, RFET coverage, eligibility state.
- Inspector tabs: Summary, Capital terms, Model evidence, RFET/NMRF, PLA and
  backtesting, Source rows, Diagnostics, Lineage, Explanation.
- Primary actions: open desk eligibility, open RFET/NMRF, compare stress-period
  movement, explain model evidence, show fallback/floor consequence.
- Hidden/deferred controls: formula internals, full P&L vectors, stress-period
  calibration detail, full ES vector pages.
- Responsive behaviour: desk, IMA amount, movement, eligibility, PLA, NMRF, and
  SES remain visible; IMCC/RFET/backtesting detail moves behind a row expander
  or inspector.

## Mode: CVA Capital

```text
Header breadcrumb: selected scope, framework CVA
Capital strip: CVA state | CVA capital | movement | counterparties | warnings
+----------------------------------------------+---------------------------+
| CVA state or counterparty grid               | Inspector: CVA evidence   |
| state panel when unavailable                 | State assertion           |
| reason | expected payload | source artifact  | Missing/feed diagnostics  |
|                                              |                           |
| counterparty | netting set | method | current| Counterparty summary      |
| baseline | movement | spread bucket | EAD    | Hedge/source rows         |
| hedge state | source count | status          | Lineage                   |
+----------------------------------------------+---------------------------+
```

- First-read summary: CVA state, CVA capital when calculated, movement,
  counterparty count, and hedge/data warning count.
- Primary grid columns when calculated: counterparty, netting set, method,
  current, baseline, movement, spread bucket, EAD/exposure proxy, hedge state,
  source count, status.
- Inspector tabs: Summary, CVA state, Source rows, Hedge evidence, Diagnostics,
  Lineage, Explanation.
- Primary actions: filter counterparty, filter method, show missing-feed
  reason, open source netting-set rows, explain CVA state.
- Hidden/deferred controls: detailed XVA trade analytics, full exposure
  profile, hedge-row pages, method internals.
- Responsive behaviour: unavailable CVA renders a focused state panel rather
  than an empty grid; calculated CVA keeps counterparty, method, current,
  movement, and status visible.

## Mode: Desk Eligibility and PLA

```text
Header breadcrumb: selected scope, mode PLA
Capital strip: eligible | amber | red | not run | capital at risk | timestamp
+----------------------------------------------+---------------------------+
| Desk eligibility matrix                      | Inspector: desk status    |
| desk | path | eligibility | PLA | metric     | Pass/amber/red reason     |
| backtesting zone | exceptions | RFET | NMRF   | PLA evidence              |
| SES | capital consequence | owner/status     | Backtesting exceptions    |
| Rates desk                                   | RFET/NMRF links           |
| Credit desk                                  | Capital consequence       |
+----------------------------------------------+---------------------------+
```

- First-read summary: eligible desk count, amber desk count, red desk count,
  desks not run, capital at risk from fallback/floor, and latest
  PLA/backtesting run time.
- Primary grid columns: desk, hierarchy path, eligibility, PLA state, PLA metric
  summary, backtesting zone, exception count, RFET coverage, NMRF count, SES,
  capital consequence, owner/status.
- Inspector tabs: Summary, PLA evidence, Backtesting, RFET/NMRF, Capital
  consequence, Source rows, Diagnostics, Lineage, Explanation.
- Primary actions: open desk, open PLA evidence, open backtesting exceptions,
  open RFET/NMRF drivers, explain eligibility.
- Hidden/deferred controls: full HPL/RTPL time series, full exception lists,
  all validation metrics, model/profile hashes unless diagnostics require them.
- Responsive behaviour: matrix collapses to desk, eligibility, PLA,
  backtesting, capital consequence, and status; detail opens in inspector.

## Mode: RFET, NMRF, and SES

```text
Header breadcrumb: selected scope, mode RFET/NMRF
Capital strip: NMRF count | newly failed RFET | SES | SES move | stale/missing
+----------------------------------------------+---------------------------+
| RFET register                                | Inspector: risk factor    |
| risk factor | family | risk class | tenor    | Modellability reason      |
| RFET state | obs count | last obs | gap      | Usage map                 |
| NMRF state | SES | movement | usage | stat   | SES bridge                |
| rf-girr-usd-5y                               | Evidence calendar         |
| rf-csr-issuer-a                              | Source rows               |
+----------------------------------------------+---------------------------+
```

- First-read summary: non-modellable risk-factor count, newly failed RFET
  count, SES total, SES movement, top SES driver, and stale/missing evidence
  count.
- Primary grid columns: risk factor, family, risk class, bucket/tenor, RFET
  state, observation count, last observation, gap state, NMRF state, SES,
  movement, desk/book usage count, status.
- Inspector tabs: Summary, Usage map, Evidence calendar, SES bridge, Source
  rows, Diagnostics, Lineage, Explanation.
- Primary actions: open usage map, open evidence calendar, show SES bridge,
  filter to selected hierarchy, explain risk factor.
- Hidden/deferred controls: raw observations, rejected observation list,
  observation-source payloads, all proxy-method metadata.
- Responsive behaviour: risk factor ID remains the sticky label; usage map
  becomes a two-column inspector section; raw observations stay paged.

## Mode: Risk-Factor and Time-Series Drivers

```text
Header breadcrumb: selected scope, selected time window
Capital strip: top RF mover | top capital driver | top SES driver | RFET change
+----------------------------------------------+---------------------------+
| Driver grid                                  | Inspector: selected driver|
| risk factor | driver type | current value    | Movement classification   |
| baseline value | value move | capital move    | Time-series panel         |
| SES move | desks/books | RFET | outlier       | Affected books/desks      |
| rf-girr-usd-5y                               | Source/evidence markers   |
+----------------------------------------------+---------------------------+
| Optional lower panel: one selected time series with current/baseline markers |
+----------------------------------------------------------------------------+
```

- First-read summary: top risk-factor mover, top capital driver, top SES
  driver, top RFET state change, and selected time window.
- Primary grid columns: risk factor, driver type, current value, baseline
  value, value movement, capital movement, SES movement, affected desks/books,
  RFET state, outlier score, evidence state.
- Inspector tabs: Summary, Time series, Affected books/desks, Capital links,
  Source rows, Diagnostics, Lineage, Explanation.
- Primary actions: change time window, switch driver type, pin risk factor,
  open affected books, explain driver.
- Hidden/deferred controls: multi-series overlays, full history export, raw
  time-series points, custom outlier threshold.
- Responsive behaviour: the lower time-series panel becomes an inspector tab;
  one selected series is shown at a time.

## Mode: Interactive Pivot and Hierarchy Analysis

```text
Header breadcrumb and capital strip remain unchanged
+----------------------------------------------+---------------------------+
| Pivot grid                                   | Inspector: subtotal       |
| active rows: hierarchy, component            | Subtotal lineage          |
| active columns: scenario                     | Child count               |
| hierarchy/component | current | move | stat  | Warning count             |
| subtotal rows labelled official/display-only | Measure definition        |
+----------------------------------------------+---------------------------+
| Pivot drawer: Rows | Columns | Filters | Measures | Sort | Reset | Copy link |
+----------------------------------------------------------------------------+
```

- First-read summary: active pivot rows, active filters, selected subtotal, row
  count, and official backend subtotal versus display-only grouped total state.
- Primary grid columns: pivot dimensions, current, baseline, movement,
  contribution, child count, warning count, status, subtotal state.
- Inspector tabs: Summary, Subtotal lineage, Children, Source rows,
  Diagnostics, Lineage, Explanation.
- Primary actions: add row dimension, add filter, collapse all, expand one
  level, reset pivot, copy pivot link.
- Hidden/deferred controls: advanced measures, more than the first supported
  row dimensions, arbitrary calculated fields, spreadsheet-like editing.
- Responsive behaviour: the pivot drawer opens from the bottom on compact
  screens; active pivot chips stay above the grid; official/display-only status
  remains visible on every subtotal row.

## AI Explanation Overlay

```text
Grid and inspector stay visible
+------------------------------------+------------------+------------------+
| Primary grid                       | Inspector        | AI explanation   |
| selected row                       | Evidence tabs    | snapshot header  |
| visible evidence                   | Source rows      | limitations      |
|                                    | Diagnostics      | findings         |
|                                    | Lineage          | evidence chips   |
|                                    |                  | next actions     |
+------------------------------------+------------------+------------------+
```

- First-read summary: explanation target, input snapshot state, generated
  timestamp, key limitation if any, and top finding.
- Primary grid columns: unchanged from the active analytical mode.
- Inspector tabs: unchanged from the active analytical mode; Explanation may be
  highlighted through canonical `inspectorTab=explanation`, but evidence tabs
  remain available.
- Primary actions: explain this view, explain selected row, choose style/depth,
  cancel generation, copy explanation with run/scope/baseline metadata.
- Hidden/deferred controls: free-form prompt expansion, regenerate reason,
  prompt template ID, input/output hashes, model identifier, audit metadata.
- Responsive behaviour: on compact screens the drawer becomes an inspector tab;
  evidence chips navigate back to the grid, source rows, desk, or risk factor.

AI drawer requirements:

- Generated commentary must cite supplied evidence identifiers.
- Limitations appear above findings when data is partial, synthetic,
  unsupported, unavailable, stale, or no-data.
- Evidence chips select or reveal the referenced row/object without changing
  the run, scope, or baseline.
- The drawer closes without clearing selected grid row or inspector state.
- Opening or closing the overlay must not change `analysisMode`, `framework`,
  `gridMode`, selected row, selected desk, selected risk factor, or selected
  hierarchy scope.

## Acceptance Checklist

- Stable shell shows header, breadcrumb/scope, capital strip, primary grid,
  inspector, and optional AI drawer.
- Top-of-house, legal-entity/business, desk/book, SA, IMA, CVA, PLA,
  RFET/NMRF/SES, risk-factor/time-series, pivot, and AI overlay surfaces each
  have a buildable low-fidelity wireframe.
- Every mode includes first-read summary, grid columns, inspector tabs, primary
  actions, hidden/deferred controls, and responsive behaviour.
- The left hierarchy rail can be expanded, compact, or hidden without losing the
  breadcrumb scope.
- AI explanation is shown as a drawer or inspector tab beside evidence and never
  as a replacement for grid, source, diagnostic, or lineage evidence.
- Wireframes preserve the source-of-truth rule: the browser displays supplied
  capital, movement, contribution, eligibility, RFET, SES, PLA, CVA, and
  subtotal values; it does not recompute them.
