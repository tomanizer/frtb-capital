# FRTB Capital Navigator UX Audit and Interaction Contract

Status: draft product contract for incremental UX hardening.

Audience: market-risk managers, desk heads, capital controllers, model owners,
and regulatory-capital analysts at a major investment bank.

Scope: FRTB capital analysis across IMA, Standardised Approach components
(SBM, DRC, RRAO), CVA when available, hierarchy rollups, model eligibility,
risk-factor evidence, attribution, source drilldown, and capital movement
analysis across run, month, quarter, and year horizons.

Companion implementation contracts:

- Capital and movement semantics:
  [`CAPITAL_AND_MOVEMENT_SEMANTICS.md`](CAPITAL_AND_MOVEMENT_SEMANTICS.md)
- Mode wireframes:
  [`MODE_WIREFRAMES.md`](MODE_WIREFRAMES.md)
- Implementation slices:
  [`IMPLEMENTATION_SLICES.md`](IMPLEMENTATION_SLICES.md)
- State and routing:
  [`NAVIGATOR_STATE_AND_ROUTING.md`](NAVIGATOR_STATE_AND_ROUTING.md)
- Result-store data boundary:
  [`RESULT_STORE_DATA_CONTRACT.md`](RESULT_STORE_DATA_CONTRACT.md)

## 1. Regulatory and Analytical Context

FRTB is not a generic dashboard problem. It is a capital-explainability problem:
the user needs to understand why the current capital number exists, whether it is
credible, what changed since the prior run or period, and which business, desk,
book, risk class, model decision, or data-quality issue caused the change.

The Basel market-risk framework emphasises several features that should shape
the user experience:

- Market risk capital exists because trading books are exposed to losses from
  movements in interest rates, credit spreads, FX, equity, commodity prices, and
  related market factors. See BIS "The market risk framework - in brief",
  January 2019.
- The revised framework is built around a stricter trading-book boundary,
  desk-level model approval, expected shortfall rather than VaR for IMA,
  non-modellable risk factor treatment, and a more risk-sensitive standardised
  approach. See BIS BCBS d457 and "The market risk framework - in brief".
- Under the Standardised Approach, capital is the sum of Sensitivities-Based
  Method capital, Default Risk Charge, and Residual Risk Add-On. See BCBS d457
  MAR20.4.
- DRC is intended to capture jump-to-default risk not captured by spread shocks,
  and is computed through gross/net JTD, risk weights, hedge benefit, buckets,
  and issuer/obligor-level logic. See BCBS d457 MAR22.
- RRAO is additive for instruments bearing residual risks, including exotic
  underlying and other residual-risk cases. See BCBS d457 MAR23.
- IMA capital depends on desk approval, PLA, backtesting, expected shortfall,
  liquidity horizons, RFET modellability evidence, and NMRF/SES treatment. See
  BCBS d457 MAR31-MAR33.
- RFET and NMRF analysis is not just model validation metadata. It is a capital
  driver: risk factors that cannot support modellability are excluded from the
  ES model and attract stress scenario capital. See BCBS d457 MAR31 and MAR33.
- CVA is a separate counterparty-credit valuation adjustment risk problem and
  should not be visually conflated with trading-book market risk unless the
  source contract explicitly links hedges or capital treatment. See BCBS d457
  MAR10/MAR25 terminology and CVA-risk-transfer treatment.

Implication: the interface should not look like a KPI wall. It should behave
like an investigation cockpit with four linked layers:

1. Scope: where in the enterprise or trading-book hierarchy am I?
2. Capital stack: which component is binding and what changed?
3. Explanation: which risk factors, desks, issuers, buckets, scenarios, or model
   eligibility decisions explain the number?
4. Evidence: what source rows, audit records, model tests, and data quality
   facts support or weaken the explanation?
5. Commentary: can a specialised analytical agent summarise the visible data,
   identify plausible drivers, and point to evidence without inventing facts?

## 2. Risk Manager Jobs To Be Done

As a senior market-risk manager, I use the Navigator for recurring and ad-hoc
questions:

- Top-of-house: "What is today's FRTB capital, and is IMA or the floor driving
  the requirement?"
- Business contribution: "Which legal entity, division, desk, Volcker desk, or
  book contributes most to the capital increase?"
- Run movement: "What changed since yesterday's official run, last month-end,
  last quarter-end, and the same month last year?"
- Component explanation: "Is the movement from SBM, DRC, RRAO, IMA, CVA, or the
  output floor?"
- SBM explanation: "Which risk class, bucket, measure, risk factor, correlation
  scenario, or sensitivity source row moved?"
- DRC explanation: "Which issuer, bucket, credit-quality band, JTD exposure,
  LGD, seniority, hedge benefit, or defaulted position drove DRC?"
- RRAO explanation: "Which exotic or residual-risk instrument caused the add-on,
  and is its classification supported?"
- IMA explanation: "Which desk, expected shortfall term, liquidity horizon,
  stress period, PLA status, backtesting zone, NMRF classification, or SES term
  drove the movement?"
- RFET explanation: "Which risk factors failed RFET, which books and businesses
  use them, and how does that failure flow into NMRF/SES capital?"
- PLA eligibility: "Which desks are eligible for IMA today, which desks are
  amber/red, and which P&L attribution or backtesting evidence caused the
  status?"
- CVA explanation: "Which counterparty, netting set, method, EAD, spread bucket,
  hedge, or no-data state explains CVA capital?"
- Model governance: "Which desks are model-approved, near failure, or falling
  back to SA because PLA/backtesting/model eligibility failed?"
- Data quality: "Are we looking at complete source coverage, stale data, missing
  RFET observations, unsupported instruments, or synthetic/no-data placeholders?"
- Audit and sign-off: "Can I show exactly which source rows support this number,
  and can I reproduce the path from top-of-house to line item?"
- Assisted explanation: "Can I ask for a concise prose explanation of this
  screen, panel, desk, risk factor, or movement, with the answer tied to the
  exact rows and evidence currently visible?"

## 3. Current UX Diagnosis

The current v2 dashboard proves that the data plumbing can produce a single
synthetic run, but it still feels clunky because it mixes navigation, filtering,
summary, and drilldown without a strong interaction contract.

Key issues:

- The hierarchy rail occupies too much horizontal space for a dense analysis
  screen and is not collapsible.
- The selected hierarchy scope is visually disconnected from the capital stack;
  the user has to infer why rows changed.
- Some controls look permanent but are not meaningful yet, especially run,
  baseline, CVA, and some scenario states.
- Search is unclear: it appears global but only affects visible grid rows.
- The table is too raw for the first analytical pass: there is no "why changed"
  mode, no movement columns, and no contribution ranking by default.
- The inspector is useful but not decisive. It needs a summary strip, evidence
  confidence, source lineage, and links between attribution rows and source rows.
- The UI does not yet distinguish "not applicable", "not available", "zero",
  "unsupported", "filtered out", and "loading".
- There is no explicit notion of an official run, provisional run, failed run,
  restatement, or baseline selection.
- RFET, NMRF/SES, and PLA are currently treated as details of IMA rather than
  as first-class analytical surfaces. That prevents the user from tracing a
  model-governance issue to risk factors, books, businesses, and capital impact.
- There is no governed AI explanation layer. If explanation is added casually,
  the product risks producing fluent prose that is not tied to source rows,
  run context, hierarchy scope, or regulatory caveats.
- The product uses system labels such as row IDs and framework tags before it
  answers the manager's first question: "what changed and why?"

The design problem is therefore not "make it prettier". The design problem is:
make investigation feel natural, fast, reversible, and trustworthy.

## 4. Product North Star

The Navigator should support one primary loop:

> Select scope -> read capital stack -> isolate movement/outlier -> explain
> contribution -> inspect evidence -> export/share the finding.

Every visible control must participate in that loop. If a control does not
change the scope, capital stack, movement analysis, explanation, evidence, or
export state, it should be removed, hidden behind an advanced menu, or shown as
disabled with a precise no-data reason.

### 4.1 Current Capital Navigator v2 Mapping

The current dashboard already has the beginnings of the right analytical model.
The UX should make these objects explicit instead of letting them leak through
as backend-shaped labels.

Current backend concepts:

- `RunSummary`: one calculation run with status, regime/profile, currency, and
  headline totals.
- `HierarchyNodeSpec`: the selected business scope. The fixture already covers
  top of house, legal entity, division, business line, desk, Volcker desk, and
  book. The current synthetic membership is rates nodes -> IMA/SBM, credit nodes
  -> DRC, and residual-risk nodes -> RRAO.
- `ScopeTotals`: scoped IMA, SBM, DRC, RRAO, SA, output floor, and binding
  values.
- `GridView` / `GridRowView`: aggregate analytical rows for SA, IMA, or CVA.
  These are the rows the user ranks, sorts, filters, and selects.
- `InspectorView`: row-specific evidence: attribution rows, source/audit rows,
  diagnostics, and framework extras.
- Attribution records: component-produced explanations of contribution and
  reconciliation status.
- Audit/source rows: the nearest available traceable detail rows. In the demo
  fixture these are synthetic; in production they should point to result-store
  artifacts or OLAP detail tables.

Current endpoint contract:

- `GET /api/runs` chooses the available run set.
- `GET /api/runs/{run_id}?hierarchyNodeId=...` returns scoped run overview and
  top-of-house-style totals.
- `GET /api/runs/{run_id}/metadata` returns hierarchy and classification
  metadata.
- `GET /api/runs/{run_id}/grid?framework=SA&scenario=Binding&hierarchyNodeId=...`
  returns scoped aggregate rows.
- `GET /api/runs/{run_id}/inspector?row_id=...&scenario=...&hierarchyNodeId=...`
  returns row-specific evidence.
- `GET /api/runs/{run_id}/nodes/{node_id}` is a future hook for hierarchy-node
  summary drilldown.

Result-store boundary:

The production Capital Navigator should meet data through `frtb-result-store`,
not through dashboard-owned synthetic aggregators. The dashboard may keep a thin
adapter while fixtures mature, but the authoritative boundary should be the
read-only result-store API and persisted marts.

Existing result-store surfaces that map directly to Navigator needs:

- Runs and status: `GET /runs`, `GET /runs/{run_id}`, `GET
  /runs/{run_id}/events`, and `GET /run-groups`.
- Top-of-house and component capital: `capital_summary`, `component_breakdown`,
  and `GET /runs/{run_id}/capital-tree`.
- Node drilldown: `GET /runs/{run_id}/nodes/{node_id}`, child nodes, measures,
  attribution, and lineage.
- Movement: `GET /runs/{run_id}/movements` backed by `movement_summary`.
- Attribution: `top_contributors`, `residual_attribution`,
  `unsupported_attribution`, and node-level attribution endpoints.
- Organisation hierarchy: `GET /runs/{run_id}/org-hierarchy`,
  `/org-hierarchy/nodes/{node_id}/children`, `/aggregate`, and `/source-rows`.
- Component marts: `ima_desk_dashboard`, `sbm_bucket_ladder`,
  `drc_issuer_contributors`, `cva_counterparty_contributors`, and
  `rrao_exposure_summary`.
- Artifact drillthrough: `GET /runs/{run_id}/artifacts`, artifact page, and
  artifact download/S3 URI handoff.

Navigator adapter responsibilities:

- Translate `NavigatorState` into result-store query parameters.
- Compose a small number of result-store calls into one UI view model when this
  improves latency and consistency.
- Preserve result-store IDs (`run_id`, `node_id`, `artifact_id`,
  `attribution_id`, hierarchy node IDs) in UI state and AI explanation
  snapshots.
- Render no-data, unsupported, stale, residual, and synthetic states based on
  result-store rows and diagnostics rather than UI inference.
- Never recalculate capital, source-row totals, official subtotals, or
  attribution in the browser.

Result-store gaps for the expanded UX:

- RFET/NMRF/SES needs dedicated marts or artifacts with canonical
  `risk_factor_id`, observation evidence, modellability state, usage mapping,
  SES amount, movement, stress period, and liquidity horizon.
- PLA/backtesting needs a desk eligibility mart with desk status, test metrics,
  thresholds/profile, exception counts, source hashes, and capital consequence.
- Time-series drivers need historical risk-factor/value/capital movement rows,
  not only current-run capital-tree rows.
- Pivot support needs a server-side aggregate query contract with allowed
  dimensions, allowed measures, subtotal reconciliation flags, and paging.
- AI explanations need a server-side snapshot builder that pulls bounded,
  entitlement-safe result-store rows and artifact pages before calling an
  external or internal model service.

Target mental model:

```text
Run
  Baseline run
  Hierarchy scope
    Capital view: Binding / Framework
      Framework: SA / IMA / CVA
        Component: SBM / DRC / RRAO / IMCC / SES / CVA method
        Analytical row: risk class, bucket, issuer, desk, book, counterparty,
        risk factor, NMRF, PLA test
          Inspector evidence: attribution, source rows, model tests, diagnostics
```

Model and risk-factor dimensions should be first-class, not hidden extras:

- IMA model dimensions: desk approval, PLA status, backtesting zone, expected
  shortfall term, liquidity horizon, stress period, RFET observation state, NMRF
  classification, SES contribution, multiplier/fallback.
- SBM risk-factor dimensions: risk class, risk measure, bucket, risk factor,
  tenor, sensitivity sign, scenario value, selected/binding scenario.
- DRC dimensions: issuer/obligor, bucket, credit quality, seniority, long/short
  JTD, LGD, hedge benefit, defaulted status.
- RRAO dimensions: instrument, residual category, base amount, add-on rate,
  classification reason, inclusion/exclusion state.
- CVA dimensions: counterparty, netting set, method, exposure profile, spread
  bucket, hedge eligibility, unsupported/no-data reason.

The frontend should therefore be a stateful investigation surface over these
objects, not a static report page. Every API response should state whether a
dimension is available, unavailable, not applicable, unsupported, synthetic, or
filtered out.

### 4.2 Major Interaction Modes

The product should expose explicit modes for the major analytical tasks instead
of forcing every workflow through the same capital grid.

Each mode should answer four questions without making the user configure the
screen first:

- What am I looking at?
- What changed?
- What explains it?
- What evidence supports or limits that explanation?

Each mode should therefore have the same quiet structure:

- First read: one compact summary strip, never a wall of cards.
- Main work area: one primary grid or matrix.
- Inspector: evidence for the selected row or object.
- Actions: explain, export/copy finding, open source rows, change baseline,
  drill down.
- Progressive disclosure: hide advanced pivots, raw rows, JSON, and secondary
  controls until the user asks for them.

#### Mode: Top-of-House Capital

Primary user: head of market risk, capital controller, senior management.

Question: what is binding today, what changed, and which component/business
caused the movement?

Screen contract:

- Header shows run, baseline, reporting date, currency, regime/profile, and data
  quality state.
- Capital stack shows binding capital, IMA, SA, output floor, CVA, movement, and
  component contribution.
- Grid defaults to component/business contribution: IMA, SA/SBM, SA/DRC,
  SA/RRAO, CVA, output floor, then legal entity/division contribution.
- Inspector explains the selected component or business contribution with
  attribution, source lineage, and diagnostics.
- AI explanation action defaults to executive summary and must cite the top
  movement rows.

UX detail:

- First read: binding capital, movement vs selected baseline, binding driver
  (`IMA`, `floor`, or explicit no-data state), top positive mover, top negative
  mover, and overall data quality.
- Primary grid columns: component/business, current, baseline, movement,
  movement %, contribution to total, contribution to movement, status, evidence
  count.
- Default sort: absolute contribution to movement, then contribution to current
  capital.
- Primary actions: change baseline, switch framework, expand top mover, explain
  view, copy executive finding.
- Inspector must show whether movement is a capital calculation movement, a
  hierarchy mix movement, a model-eligibility movement, or a data-quality
  movement.
- Keep streamlined: show no more than five headline numbers. Put distribution,
  scenario comparison, and raw rows behind drilldown.

#### Mode: Legal Entity and Business Capital

Primary user: legal-entity risk manager, finance controller, business-aligned
risk manager.

Question: which legal entity, division, business line, desk, or book explains
this capital and movement?

Screen contract:

- Scope rail starts expanded enough to show the selected legal entity path, but
  can collapse to a breadcrumb.
- Grid pivots by business hierarchy: legal entity -> division -> business line
  -> desk -> Volcker desk -> book.
- Columns show current capital, baseline capital, movement, contribution to
  selected parent, contribution to top-of-house, and data state.
- Users can expand/collapse hierarchy nodes inline, aggregate at any level, and
  filter to a subtree without changing the official run.
- Selecting a business node updates the capital stack and inspector to the node
  scope; it does not merely highlight a tree row.

UX detail:

- First read: selected hierarchy path, scoped binding capital, movement,
  percentage of top-of-house, number of child desks/books, and warning count.
- Primary grid columns: hierarchy node, node type, current, baseline, movement,
  share of parent, share of top-of-house, child count, warning count, model/data
  state.
- Inline tree rows must support expand/collapse without reloading the whole
  page. Collapsed nodes show reconciled subtotal and mixed-state badges.
- Filters should be expressed as chips: `LE-DEMO`, `FICC`, `Rates`, `IMA only`,
  `warnings`, `movers`.
- Inspector for a hierarchy node should show component mix, child contribution,
  data completeness, and the top three drivers in that scope.
- Keep streamlined: do not show every hierarchy attribute as a column. Put
  ownership metadata, long IDs, and entitlement details in the inspector.

#### Mode: Desk and Book Capital

Primary user: desk head, desk market-risk manager, model owner.

Question: what capital does my desk/book generate, which model path is used, and
which source rows or risk factors explain it?

Screen contract:

- Desk view shows IMA eligibility, IMA capital, SA fallback capital, SES, SBM,
  DRC, RRAO, CVA/no-data, and binding/floor impact where applicable.
- Book view shows book-level contribution and links to instruments/source rows,
  risk factors, RFET usage, and NMRF/SES terms.
- Desk and book selectors are derived from hierarchy nodes, not separate
  duplicate filters.
- If a desk contains multiple books with different model/data states, the grid
  must show mixed-state badges and allow book-level drilldown.

UX detail:

- First read: desk/book capital, model path (`IMA`, `SA fallback`, `floor`,
  `no-data`), movement, eligibility state, SES/NMRF amount, and largest source
  driver.
- Primary grid columns: book/component/risk driver, current, baseline, movement,
  model state, RFET/NMRF state, PLA/backtesting state, source count, status.
- Primary actions: open eligibility, open RFET/NMRF, open source rows, compare
  to prior run/month, explain selected desk/book.
- Book rows should expose source system coverage and last source timestamp
  because stale book inputs can masquerade as capital stability.
- Inspector should start with "why this desk/book number exists" and then split
  into capital, model evidence, source rows, and diagnostics.
- Keep streamlined: desk users should not start in top-of-house mode. The app
  should deep-link directly to a desk/book view with the hierarchy rail compact.

#### Mode: IMA Capital and Model Evidence

Primary user: IMA model owner, market-risk analytics, validation.

Question: how do IMCC, SES/NMRF, liquidity horizons, stress periods, PLA, and
backtesting combine into the model capital result?

Screen contract:

- Grid defaults to desk rows, then risk class / ES term / SES term drilldowns.
- Inspector shows IMCC, constrained/unconstrained ES terms, liquidity horizon,
  stress period, multiplier, PLA/backtesting state, RFET/NMRF links, and source
  lineage.
- NMRF and PLA warning badges are clickable and take the user to the relevant
  dedicated mode with the same desk scope.
- Movement view separates pure ES movement from SES/NMRF movement and model
  eligibility/fallback movement.

UX detail:

- First read: IMA capital, IMCC, SES, multiplier/fallback state, eligible desk
  count, amber/red desk count, and model-evidence freshness.
- Primary grid columns: desk, current IMA, baseline IMA, movement, IMCC, SES,
  NMRF count, PLA state, backtesting zone, RFET coverage, eligibility state.
- Secondary drilldown columns by desk: broad risk class, liquidity horizon,
  stress period, ES term, SES term, source coverage.
- Primary actions: open desk eligibility, open RFET/NMRF, compare stress-period
  movement, explain model evidence, show fallback/floor consequence.
- Inspector should lead with whether the desk is allowed to use IMA and why,
  then show capital terms. A desk that is ineligible should not make the user
  hunt for that fact in a diagnostics tab.
- Keep streamlined: formula details, stress-period calibration internals, and
  full P&L vectors belong behind "show model evidence" or source drilldown.

#### Mode: Standardised Approach Capital

Primary user: capital analyst, desk risk manager, standardised-approach owner.

Question: is SA driven by SBM sensitivities, DRC default risk, or RRAO residual
risk, and where is the source evidence?

Screen contract:

- SA stack splits SBM, DRC, and RRAO.
- SBM view pivots by risk class, measure, bucket, risk factor, scenario, and
  sensitivity source row.
- DRC view pivots by portfolio type, bucket, issuer/obligor, credit quality,
  gross/net JTD, LGD, and hedge benefit.
- RRAO view behaves like a classification review queue by residual category,
  instrument, base amount, add-on rate, and inclusion/exclusion reason.
- Scenario selection affects SBM/SA values where scenario data exists and is
  included in cache/state.

UX detail:

- First read: SA total, SBM/DRC/RRAO split, selected SBM scenario, movement,
  largest component mover, and unsupported/no-data component count.
- Primary grid columns: component, risk class/category, bucket, current,
  baseline, movement, scenario values where applicable, source count, status.
- SBM default rows: risk class and measure, with bucket/risk-factor drilldown.
- DRC default rows: portfolio type and bucket, with issuer/obligor drilldown.
- RRAO default rows: residual category and instrument count, with
  classification drilldown.
- Primary actions: scenario toggle, component filter, top movers, source rows,
  explain selected component.
- Keep streamlined: do not show all SBM scenario columns in every SA view if the
  selected task is DRC or RRAO. Scenario detail should appear only for SBM rows
  or when the user selects scenario comparison.

#### Mode: CVA Capital

Primary user: counterparty-credit market-risk manager, XVA/CVA controller.

Question: does CVA exist for this scope, which counterparty/netting set drives
it, and are hedges or method limitations visible?

Screen contract:

- CVA mode must first classify the state: no exposures, feed missing, not
  implemented, unsupported method, or calculated.
- When calculated, grid pivots by counterparty, netting set, method, spread
  bucket, hedge eligibility, and exposure profile.
- CVA is visually separate from trading-book market risk but visible in
  top-of-house capital context.
- Missing CVA must not be rendered as zero capital unless the backend supplies a
  positive no-exposure assertion.

UX detail:

- First read: CVA state (`calculated`, `no exposure`, `feed missing`,
  `unsupported`, `not in fixture`), CVA capital if calculated, movement,
  counterparty count, and hedge/data warning count.
- Primary grid columns when calculated: counterparty, netting set, method,
  current, baseline, movement, spread bucket, EAD/exposure proxy, hedge state,
  source count, status.
- Primary actions: filter counterparty, filter method, show missing feed reason,
  open source netting-set rows, explain CVA state.
- Inspector should distinguish "zero due to no exposure" from "unavailable" and
  show the backend assertion or missing artifact that supports the state.
- Keep streamlined: if CVA is unavailable in the selected run, render a focused
  no-data panel with reason and expected payload, not an empty grid.

#### Mode: Desk Eligibility and PLA

Primary user: desk supervisor, model governance, validation, risk control.

Question: which desks are IMA-eligible, which are close to failure, and what is
the capital consequence?

Screen contract:

- Desk eligibility matrix rows are desks; columns are approval state, PLA state,
  PLA metrics, backtesting zone/exceptions, RFET coverage, NMRF count, SES,
  fallback state, and capital movement.
- Desk detail shows HPL/RTPL evidence, unexplained P&L diagnostics,
  backtesting-window exceptions, source run IDs, and model/profile hashes.
- Amber/red states expose the exact failing test and link to affected books,
  risk factors, and capital rows.
- A desk can be filtered by legal entity/division/business line and then
  expanded to books without losing PLA context.

UX detail:

- First read: eligible desk count, amber desk count, red desk count, desks not
  run, capital at risk from fallback/floor, and latest PLA/backtesting run time.
- Primary grid columns: desk, hierarchy path, eligibility, PLA state, PLA metric
  summary, backtesting zone, exception count, RFET coverage, NMRF count, SES,
  capital consequence, owner/status.
- Default sort: red desks by capital consequence, then amber desks by proximity
  to threshold.
- Primary actions: open desk, open PLA evidence, open backtesting exceptions,
  open RFET/NMRF drivers, explain eligibility.
- Desk detail should show only the metrics needed to understand pass/amber/red
  first; full HPL/RTPL time series and exception lists are secondary tabs.
- Keep streamlined: avoid showing all validation metrics in the matrix. Use a
  compact state badge plus one proximity number, then put detail in inspector.

#### Mode: RFET, NMRF, and SES

Primary user: RFET owner, NMRF capital analyst, IMA model owner, desk risk
manager.

Question: which risk factors fail RFET, which businesses/books use them, and how
much SES capital do they drive?

Screen contract:

- RFET register rows are canonical risk factors, not display labels.
- Columns show risk-factor family, risk class, curve/surface/cube, tenor,
  currency/issuer/counterparty, observation count, last observation, gap state,
  RFET result, NMRF state, SES, movement, and usage count.
- Usage panel maps risk factor -> book -> desk -> business line -> legal entity.
- SES panel ranks non-modellable risk factors by current capital, movement, and
  contribution to IMA/binding capital.
- Evidence calendar shows observation dates and missing windows; it must
  distinguish missing source, stale source, failed RFET, and intentionally
  non-modellable classification.
- Selecting a risk factor keeps `riskFactorId` stable across RFET, NMRF, IMA,
  SBM, and source-row views.

UX detail:

- First read: non-modellable risk-factor count, newly failed RFET count, SES
  total, SES movement, top SES driver, and stale/missing evidence count.
- Primary grid columns: risk factor, family, risk class, bucket/tenor, RFET
  state, observation count, last observation, gap state, NMRF state, SES,
  movement, desk/book usage count, status.
- Default sort: SES movement, then current SES, then newly failed RFET.
- Primary actions: open usage map, open evidence calendar, show SES bridge,
  filter to selected hierarchy, explain risk factor.
- Usage map should be a simple two-column lineage: left side risk factor
  evidence, right side books/desks/businesses using it. Avoid graph complexity
  until the table workflow is strong.
- Inspector should show why the risk factor is modellable or non-modellable,
  where it is used, and how it contributes to SES. These three facts must be on
  the first inspector screen.
- Keep streamlined: do not expose all observation rows by default. Show count,
  latest date, gaps, and rejected count first; raw observations are a drilldown.

#### Mode: Risk-Factor and Time-Series Drivers

Primary user: market-risk analyst, desk risk manager, model owner.

Question: which risk factors moved, which books use them, and did the move
translate into capital, SES, PLA, or scenario changes?

Screen contract:

- Driver grid ranks risk factors by capital movement, sensitivity movement, SES
  movement, RFET status change, and time-series outlier score.
- Time-series panel shows current vs baseline vs history for risk-factor value,
  sensitivity/exposure proxy, capital contribution, RFET observation state, and
  SES where relevant.
- Users can switch between daily run movement, month-end movement, quarter-end
  movement, and year-on-year movement.
- Risk-factor selection links to all books/desks using the factor and all
  capital rows where it contributes.
- Outlier labels must say whether the outlier is market-data movement,
  sensitivity/exposure movement, model-evidence movement, or capital aggregation
  movement.

UX detail:

- First read: top risk-factor mover, top capital driver, top SES driver, top
  RFET state change, and selected time window.
- Primary grid columns: risk factor, driver type, current value, baseline value,
  value movement, capital movement, SES movement, affected desks/books, RFET
  state, outlier score, evidence state.
- Time-series panel should show one selected series at a time with synchronized
  markers for baseline, current run, RFET observation gaps, SES changes, and
  capital jumps.
- Primary actions: change time window, switch driver type, pin risk factor,
  open affected books, explain driver.
- Inspector should answer whether the risk factor moved, exposure moved, model
  evidence changed, or aggregation changed. These are different operational
  follow-ups.
- Keep streamlined: avoid multi-series chart clutter. Start with one selected
  risk factor and small comparison overlays only when explicitly chosen.

#### Mode: Interactive Pivot and Hierarchy Analysis

Primary user: power analyst, controller, business risk manager.

Question: can I reshape the view quickly without losing lineage or creating
unreconciled aggregates?

Screen contract:

- User can pivot rows by hierarchy, component, risk class, desk, book, risk
  factor, issuer/counterparty, scenario, model state, and data state.
- User can collapse and expand hierarchy nodes inline; collapsed parents show
  reconciled subtotal, child count, warning count, and mixed-state badges.
- Filters are explicit chips with scope: hierarchy filter, component filter,
  model-state filter, risk-factor filter, source-data filter.
- Aggregates must remain server-backed or result-store-backed. The browser may
  group displayed rows for convenience, but official subtotal rows must come
  from the backend when used for sign-off.
- Pivot state is shareable in the URL and included in AI explanation snapshots.

UX detail:

- First read: active pivot rows, active filters, selected subtotal, row count,
  and whether totals are official backend totals or display-only grouped totals.
- Pivot controls should be a compact drawer, not a permanent side panel:
  `Rows`, `Columns`, `Filters`, `Measures`, `Sort`.
- Safe default pivots:
  - capital by hierarchy/component;
  - movement by hierarchy/component;
  - RFET/NMRF by hierarchy/risk class;
  - PLA by hierarchy/eligibility state;
  - source diagnostics by hierarchy/source state.
- Primary actions: add row dimension, add filter, collapse all, expand one
  level, reset pivot, copy pivot link.
- Inspector for a pivot subtotal should show subtotal lineage, child count,
  warning count, measure definition, and official/display-only status.
- Keep streamlined: do not build a spreadsheet clone. Limit row dimensions and
  visible measures for the first implementation; advanced pivoting can wait
  until server-backed aggregation is robust.

## 5. Information Architecture

The app should have five durable regions.

### 5.1 Header: Run Context and Global Status

Purpose: tell the user what dataset and calculation context they are reviewing.

Must show:

- Run label, run ID, run status, calculation date, publication timestamp.
- Official/provisional/restated flag.
- Active baseline: prior run, prior business day, month-end, quarter-end,
  year-on-year, or custom.
- Jurisdiction/profile: US NPR 2.0, Basel, CRR3, PRA, or internal comparison.
- Data state: complete, partial, synthetic, stale, failed, or unavailable.

Controls:

- Run picker: only visible as a picker when multiple runs exist.
- Baseline picker: hidden until baseline data exists; then exposed as a compact
  segmented/date menu.
- Currency/reporting basis: only visible when multi-currency or reporting-base
  differences exist.

Interaction contract:

- Changing run reloads all downstream data and resets row selection.
- Changing baseline keeps scope/framework/row if still valid, but recomputes
  movement and contribution columns.
- Run and baseline selections must be part of every API cache key.

UX detail:

- The header should read as one sentence of context: run, date, scope, baseline,
  profile, and data state.
- Avoid putting all selectors in the header. Only run, baseline, scope
  breadcrumb, and global status belong there.
- If there is only one run, show a run label instead of a disabled picker.
- If there is no baseline, show `No baseline selected` and hide movement
  controls until a baseline exists.
- Header status badges must be clickable only when they open useful diagnostics.

### 5.2 Scope Rail: Enterprise and Trading-Book Hierarchy

Purpose: choose the organisational/business scope being analysed.

Hierarchy levels:

- Top of house / group.
- Legal entity.
- Business division, eg FICC, Equities, FX, Treasury.
- Business line.
- Desk.
- Volcker desk where applicable.
- Book / trading book.
- Optional portfolio or strategy tags when available.

Required behaviour:

- Collapsible rail with three widths:
  - expanded: labels, node type, badges, small totals;
  - compact: icons/initials and selected-path affordance;
  - hidden: breadcrumb remains in header.
- Keyboard navigable tree: up/down, left/right collapse, enter select.
- Search within hierarchy, not mixed with grid search.
- Pin/favourite frequently used scopes.
- Show badges for material states: model-approved, fallback, no-data, warning,
  stale, new, moved materially.

Interaction contract:

- Selecting a hierarchy node updates:
  - header breadcrumb;
  - capital stack KPIs;
  - grid rows;
  - inspector selected row, reset to first valid row;
  - movement/outlier panels;
  - API cache key: `runId`, `baselineRunId`, `hierarchyNodeId`.
- Collapsing the rail must not change selected scope.
- If the selected framework has no data for the scope, the grid shows one
  explicit no-data row with the reason.

Implementation slice:

- Add a collapse toggle and local-storage persistence.
- Move selected scope into a breadcrumb in the header/context bar.
- Split hierarchy search from grid search.

UX detail:

- Default state should be compact after first use. The selected path remains
  visible in the breadcrumb.
- Expanded rail should prioritise labels and warning badges, not totals for
  every node.
- Compact rail should support keyboard and hover/focus tooltips.
- Search result rows should show path context so `Rates` under different legal
  entities is not ambiguous.
- The rail is navigation, not a filter drawer. Analytical filters belong above
  the grid as chips.

### 5.3 Capital Stack: Binding View and Component Contribution

Purpose: answer "what number matters and what explains it?"

Must show:

- Binding capital.
- IMA capital.
- SA capital.
- Output floor value and binding side.
- CVA capital or no-data state.
- Movement vs baseline: amount and percentage.
- Contribution to movement by component.

Capital stack should be displayed as a compact horizontal strip or slim stacked
bar, not as large cards. The user needs table space.

Interaction contract:

- Clicking IMA selects framework IMA.
- Clicking SA selects framework SA.
- Clicking CVA selects framework CVA.
- Clicking output floor opens an explanation panel that shows the floor amount
  and whether the floor is binding. In the v2 demo, the explanatory text may
  show the fixed non-regulatory `0.725` display multiplier used by the fixture;
  production views should show a multiplier only when it is supplied by the
  persisted run payload.
- Movement badges use baseline data only. If no baseline exists, they render as
  unavailable, not zero.

Required states:

- `ok`: complete and reconciled.
- `partial`: some components missing.
- `no_data`: component not present in run.
- `unsupported`: known component not implemented in selected profile.
- `stale`: source date older than run date.
- `synthetic`: fixture/demo data.

UX detail:

- The stack should be one horizontal strip with tabular numerals and small
  movement badges.
- Only the binding value gets visual emphasis. Other numbers stay comparable but
  quieter.
- Component labels should be clickable if they change the framework/mode.
- Floor explanation should be a small popover or inspector selection, not a
  separate page.
- No-data components should remain visible only if they matter to the capital
  question; otherwise place them in diagnostics.

### 5.4 Workbench Grid: Analysis Table

Purpose: rank, compare, filter, and select aggregate rows.

The grid should support modes, because no single table serves all analytical
questions.

Mode A: Capital Stack

- Rows: framework -> component -> risk class -> bucket/desk/book.
- Columns: current capital, baseline capital, movement, movement %, contribution
  to total, contribution to movement, status.

Mode B: Drivers and Outliers

- Rows: drivers ranked by absolute movement or contribution.
- Columns: current, baseline, movement, z-score or percentile, source count,
  evidence state.

Mode C: Risk Factor / Model Evidence

- Rows: risk factor, curve, issuer, counterparty, bucket, or NMRF group.
- Columns: modellability, RFET observations, SES, liquidity horizon, PLA
  linkage, source coverage.

Mode D: Source Rows

- Rows: raw or lightly normalised source rows.
- Columns vary by component, but must keep source ID, amount, component,
  calculation branch, and status visible.

Initial MVP should implement Mode A and a simple Drivers view before adding
high-volume raw source browsing.

Interaction contract:

- Grid row selection is the only way to change the inspector's primary object.
- Changing scope/framework/scenario/baseline resets row selection to the first
  valid row unless the previous row still exists.
- Search filters rows in the active grid mode only.
- Sort is stable and deterministic.
- Columns must never imply values exist when the fixture/backend does not expose
  them.
- Every row must expose:
  - stable row ID;
  - display label;
  - component/framework;
  - hierarchy scope;
  - current amount;
  - baseline amount if selected;
  - movement if available;
  - data state;
  - drilldown availability.

UX detail:

- The grid should keep one sticky label column and right-aligned tabular numeric
  columns.
- Default density should be high but readable: compact rows, clear hover/focus,
  no oversized cards inside the workbench.
- Controls above the grid should fit one line: mode, scenario when applicable,
  top-movers toggle, search, and active filter chips.
- Column presets should be task-based: `Capital`, `Movement`, `Evidence`,
  `Source`, not user-authored column chaos in the first version.
- Empty grids need one reason row and one next action.

### 5.5 Inspector: Evidence and Drilldown

Purpose: prove or disprove the explanation for the selected row.

The inspector should not be a generic JSON dump. It should have a clear
hierarchy of evidence:

1. Summary: current, baseline, movement, contribution, status.
2. Attribution: contribution rows and method used.
3. Source rows: the rows that reconcile to the selected aggregate.
4. Model/data tests: PLA, backtesting, RFET/NMRF, SES, stress period, DRC
   issuer evidence, RRAO classification, CVA exposure/hedge evidence.
5. Diagnostics: unsupported, missing, stale, residual, partial, synthetic.
6. Lineage: input hash, profile hash, calculation timestamp, source system.

Interaction contract:

- Inspector must always be scoped to the selected hierarchy node and selected
  grid row.
- Source-row tabs must never relabel unrelated component-wide rows as if they
  belong to a selected bucket or book.
- Empty tabs should be hidden unless the absence itself is analytically useful.
- Diagnostics should be ordered by materiality: error, review, warning, info.
- Each diagnostic needs a direct next action, such as "open source rows", "show
  missing fields", "switch to top-of-house", or "view unsupported feature".

UX detail:

- Inspector starts with a compact summary strip: selected object, current,
  baseline, movement, status, evidence count.
- Tabs should be mode-aware but predictable: Summary, Attribution/Capital,
  Source rows, Model evidence, Diagnostics, Lineage.
- The first visible tab should be the one most likely to answer "why" for the
  selected row. Do not always default to raw attribution.
- Source rows should be paged and bounded, with source count and filter chips
  visible above the table.
- JSON should be last-resort diagnostic output, not a normal tab.

### 5.6 Assisted Explanation Panel

Purpose: let the user request a controlled prose explanation of the current
screen, panel, row, desk, risk factor, or movement without losing the analytical
context that produced it.

This feature should feel like asking a senior market-risk analyst to comment on
the evidence already on screen. It must not feel like an open-ended chatbot.

Trigger points:

- Capital stack: explain binding capital, floor relationship, component
  contribution, and movement vs baseline.
- Workbench grid: explain selected rows, top movers, outliers, and no-data
  states.
- Inspector: explain attribution, source rows, diagnostics, and evidence gaps.
- RFET/NMRF panel: explain failing risk factors, book/business usage, SES
  contribution, and remediation state.
- PLA desk eligibility panel: explain desk status, PLA/backtesting evidence,
  fallback risk, and capital impact.

User controls:

- Button label: `Explain this view` for a screen/panel and `Explain selected row`
  for a selected object.
- Optional explanation style:
  - executive summary;
  - risk-manager commentary;
  - model-validation commentary;
  - source-data diagnostic;
  - movement/outlier explanation.
- Optional depth:
  - short: three to five bullets;
  - standard: prose summary plus evidence bullets;
  - detailed: structured analysis with caveats and next actions.

Interaction contract:

- The request is created from the current `NavigatorState`, not from free text
  alone.
- The user can add a short question, but the backend controls the data payload
  and prompt template.
- The explanation is generated from a frozen input snapshot: run, baseline,
  hierarchy node, framework, scenario, analysis mode, selected row, visible
  aggregates, inspector evidence, diagnostics, and source-row samples.
- The response must cite internal evidence identifiers such as row IDs, source
  IDs, risk-factor IDs, desk IDs, diagnostic codes, or attribution IDs.
- The response must distinguish fact, inference, limitation, and recommended
  next action.
- The response must never present proposed-rule/comparison outputs as final
  regulatory capital.
- The response must not recompute capital. It may explain supplied numbers and
  request missing data, but calculation remains in the capital engines.
- If the visible data is partial, synthetic, stale, unsupported, or missing, the
  answer must lead with that limitation.
- The user can copy the explanation, but copied text includes run ID, timestamp,
  scope, baseline, and an "AI-generated analytical commentary" label.

Response shape:

```text
AiExplanation
  explanationId
  runId
  baselineRunId | null
  hierarchyNodeId
  analysisMode
  targetType: view | panel | row | desk | risk_factor | source_rows
  targetId
  model
  promptTemplateId
  inputSnapshotHash
  generatedAt
  status: complete | partial | refused | failed
  summary
  findings[]
    severity: info | watch | warning | critical
    claim
    evidenceRefs[]
    confidence: low | medium | high
  limitations[]
  nextActions[]
```

Backend/API contract:

- `POST /api/runs/{run_id}/explanations` creates an explanation request.
- Request body includes target type, target ID, explanation style, depth, and
  optional user question.
- Backend expands the request into a governed prompt payload from server-side
  data. The browser must not send arbitrary hidden datasets or credentials to
  the model provider.
- The service may call the OpenAI Responses API or an internal completion/agent
  service, but the dashboard contract is provider-neutral.
- Use structured output for the model response so the UI can render findings,
  evidence links, limitations, and next actions deterministically.
- Store prompt template ID, input snapshot hash, output hash, model identifier,
  requestor, and timestamp for audit.
- Explanation generation should be asynchronous for large panels and cancellable
  from the UI.
- Cached explanations may be reused only when the input snapshot hash matches.

Prompt/data guardrails:

- Include only the rows needed for the selected view. For raw source tables, send
  aggregate summaries plus bounded samples unless the user explicitly requests a
  source-row explanation.
- Redact or omit entitlements, user IDs, credentials, and non-displayable source
  fields.
- Add a system instruction that the agent is an FRTB analytical assistant, not a
  regulatory authority, not a capital calculator, and not a control owner.
- Require the agent to say "not available in this view" rather than infer missing
  fields.
- Require the agent to cite every material claim to supplied evidence IDs.
- Add a refusal path for prompts that ask for unsupported regulatory
  conclusions, data outside the user's entitlement, or capital recomputation.

UI rendering:

- Render the answer in a side drawer or inspector tab, not as a modal that blocks
  the investigation.
- Show an evidence sidebar with clickable row/source/risk-factor references.
- Show generated timestamp, model/agent name, and input snapshot label.
- Show limitations above findings when data quality is weak.
- Allow regenerate only with an explicit reason or changed state; do not create
  silent alternate answers for the same snapshot.

UX detail:

- The AI drawer should open on the right side of the inspector and keep the
  selected row visible.
- Generated findings should be short by default: headline, evidence-backed
  bullets, limitations, next actions.
- Evidence references should be clickable chips that select the referenced row,
  source line, desk, or risk factor.
- The answer should never replace the grid or inspector. It is commentary on
  evidence, not the evidence itself.

## 6. Component-Specific UX Contracts

### 6.1 Standardised Approach Overview

SA is composed from SBM, DRC, and RRAO. It should be shown as a stack, not a
single opaque number.

User questions:

- Is the SA movement driven by sensitivities, default risk, or residual risk?
- Which risk class or bucket dominates the move?
- Which component has missing or unsupported detail?

Required controls:

- Component selector: SBM / DRC / RRAO / combined.
- Correlation scenario for SBM: binding, base, high, low.
- Movement baseline.

Required drilldown:

- SBM -> risk class -> risk measure -> bucket -> risk factor -> sensitivity row.
- DRC -> portfolio type -> bucket -> issuer/obligor -> net JTD/gross JTD/LGD.
- RRAO -> residual category -> instrument -> classification reason.

UX detail:

- The SA overview should answer component mix before showing any risk-factor
  detail.
- Analysts need to see whether the SA total changed because one component moved
  or because hierarchy scope/model fallback changed.
- First drilldown should be component-level; second drilldown should be the
  natural component dimension: SBM risk class, DRC bucket, RRAO category.
- Keep streamlined: avoid mixing SBM scenario controls with DRC/RRAO rows unless
  the selected row is SBM.

### 6.2 SBM UX

SBM is sensitivity-driven and scenario-driven.

Surface:

- Risk classes: GIRR, CSR non-securitisation, CSR securitisation CTP/non-CTP,
  equity, commodity, FX.
- Measures: delta, vega, curvature.
- Buckets and risk factors.
- Correlation scenario: base/high/low and selected/binding.

Interaction contract:

- Scenario selection changes current capital where scenario data exists.
- Scenario columns remain visible for comparison but are not a substitute for
  active scenario selection.
- Curvature rows must not be visually confused with delta/vega sensitivities.
- Unsupported risk class or method appears as unsupported, not zero.

UX detail:

- Analysts need to see risk class, measure, bucket, scenario, sensitivity amount,
  weighted sensitivity/capital contribution, and source count.
- Risk-factor rows should show canonical risk-factor ID and label; long curve or
  tenor details can sit in the inspector.
- Scenario comparison should be a compact segmented control plus optional
  columns, not four parallel grids.
- Curvature should use distinct labels and row grouping because its source logic
  differs from delta/vega.
- Keep streamlined: source CRIF/sensitivity rows are drilldown; the first SBM
  screen is risk class/measure/bucket contribution.

### 6.3 DRC UX

DRC is issuer/default-risk driven.

Surface:

- Portfolio type: non-securitisation, securitisation non-CTP, CTP.
- Bucket.
- Issuer/obligor/legal entity.
- Credit quality/rating band.
- Long/short net JTD, gross JTD, LGD, hedge benefit, defaulted status.

Interaction contract:

- Bucket selection filters attribution and source rows to that bucket.
- Issuer selection filters to that issuer and shows all contributing positions.
- Defaulted and unrated positions are visually distinct.
- Hedge benefit and offsetting must be explainable; do not bury HBR in raw JSON.
- DRC totals should always reconcile to bucket-level rows before issuer-level
  rows are shown.

UX detail:

- Analysts need to see bucket, issuer/obligor, credit quality, long JTD, short
  JTD, net JTD, LGD, gross capital, hedge benefit, and final contribution.
- Defaulted, unrated, and concentrated issuers need visible flags.
- Issuer drilldown should show all positions/source rows contributing to the
  selected issuer and distinguish hedge/offset rows from exposure rows.
- Movement view should identify whether DRC moved because exposure changed,
  rating/quality changed, default status changed, LGD changed, or hedge benefit
  changed.
- Keep streamlined: do not show all DRC formula intermediates in the main grid;
  show them in the issuer/bucket inspector.

### 6.4 RRAO UX

RRAO is classification-driven and often qualitative.

Surface:

- Residual-risk category: exotic underlying or other residual risk.
- Instrument classification.
- Add-on rate and base amount.
- Inclusion/exclusion reason.

Interaction contract:

- RRAO rows should read like a classification review queue.
- Excluded instruments should be visible only when a "show excluded" toggle is
  enabled.
- Classification evidence should be in the inspector summary, not only source
  rows.
- Residual/additive attribution should be explicitly labelled as standalone or
  residual, not analytical Euler.

UX detail:

- Analysts need to see instrument/category, inclusion state, base amount, add-on
  rate, capital amount, classification reason, and review status.
- RRAO should feel like a compact review queue: included, excluded, needs
  review, unsupported.
- Movement view should identify new residual-risk instruments, removed
  instruments, changed base amount, changed classification, and changed rate.
- Inspector should show the classification evidence and the source rows that
  support inclusion/exclusion.
- Keep streamlined: excluded instruments stay hidden until the user enables
  `show excluded` or is investigating a movement.

### 6.5 IMA UX

IMA is desk/model-evidence driven.

Surface:

- Desk eligibility and approval state.
- IMCC / expected shortfall terms.
- Liquidity horizon and stress period.
- PLA test status and metrics.
- Backtesting zone.
- NMRF classification and SES contribution.
- Fallback or capital multiplier effects.

Interaction contract:

- Desk row is the main unit of IMA analysis.
- PLA/backtesting failures should visually connect to fallback/capital impact.
- NMRF and SES must be first-class drilldowns, not incidental JSON fields.
- Stress-period selection must be explainable: window, dates, observations,
  proxy/calendared status.
- Model evidence should always identify whether the result is exact,
  policy-proxy, missing, unsupported, or synthetic.

UX detail:

- Analysts need to see IMCC, SES, multiplier/fallback, desk eligibility, PLA,
  backtesting, RFET coverage, and stress-period state in one row per desk.
- The selected desk inspector should lead with capital consequence: eligible
  IMA, fallback risk, or no-data.
- ES term details should be grouped by risk class/liquidity horizon; NMRF/SES
  details should be grouped by risk factor and aggregation bucket.
- Movement view should separate market-risk movement from model-governance
  movement.
- Keep streamlined: model implementation diagnostics and full vectors are
  secondary evidence, not first-screen content.

### 6.6 CVA UX

CVA should not be a blank placeholder forever. Even when no payload exists, the
UX must distinguish:

- not implemented;
- implemented but no exposures in selected scope;
- source feed missing;
- unsupported method;
- synthetic run does not include CVA.

When data exists, CVA should support:

- counterparty and netting set;
- BA-CVA vs SA-CVA method;
- EAD/exposure profile;
- spread bucket;
- hedge eligibility;
- wrong-way-risk or method adjustment where supported;
- source trade/netting-set rows.

UX detail:

- Analysts need a reasoned CVA state before any empty table: calculated, no
  exposure, missing feed, unsupported method, not in run, or fixture limitation.
- When calculated, first screen should show counterparties/netting sets ranked by
  capital and movement.
- Hedges should be visible as eligibility/status, with drilldown to hedge rows
  only when needed.
- Movement view should separate exposure/profile movement, spread movement,
  hedge movement, and method/data-state movement where data supports it.
- Keep streamlined: do not mix detailed XVA trade analytics into the first CVA
  capital page.

## 7. Movement and Baseline Contract

Movement analysis is the missing centre of the product. A risk manager rarely
looks only at an absolute capital number; they ask why it changed.

Baseline types:

- Previous official run.
- Previous business day.
- Month-end.
- Quarter-end.
- Year-on-year.
- Custom run.

Movement values:

- current amount;
- baseline amount;
- absolute movement;
- percentage movement;
- contribution to total movement;
- rank;
- sign and materiality band.

Interaction contract:

- Baseline selection is global and included in every query.
- Movement columns are hidden or marked unavailable when no baseline exists.
- "Zero movement" means both values exist and are equal.
- "No baseline" means baseline is unavailable.
- "New" means current exists and baseline does not.
- "Dropped" means baseline exists and current does not.
- Restated baselines must be labelled.

Outlier logic:

- Near-term: rank by absolute movement and percentage movement.
- Later: add historical percentile, z-score, or business-defined thresholds.
- Every outlier must link to a traceable row and source evidence.

UX detail:

- Movement should always name the baseline in the column header, eg `Movement vs
  prior run` or `Movement vs month-end`.
- Every movement row should classify the driver when possible: market-data,
  exposure/sensitivity, hierarchy mix, model evidence, eligibility/fallback,
  source-data, or unsupported/no-data.
- Top movers should be a mode, not a separate dashboard. It should reuse the
  same grid and inspector state.
- Percentage movement should be suppressed or marked unstable when the baseline
  is near zero.
- Keep streamlined: show one active baseline at a time. Multi-baseline
  comparison can be a secondary view.

## 8. Data and Source Contract

The Navigator should treat every capital number as a materialised view over
source data, not as a loose UI aggregate.

Minimum source fields:

- `run_id`
- `baseline_run_id` where applicable
- `hierarchy_node_id`
- `framework`
- `component`
- `row_id`
- `source_system`
- `source_id`
- `calculation_branch`
- `capital_amount`
- `currency`
- `data_state`
- `input_hash`
- `profile_hash`
- `calculation_timestamp`

Minimum AI explanation fields:

- `explanation_id`
- `run_id`
- `baseline_run_id` where applicable
- `hierarchy_node_id`
- `analysis_mode`
- `target_type`
- `target_id`
- `prompt_template_id`
- `input_snapshot_hash`
- `output_hash`
- `model_id`
- `agent_profile`
- `requested_by`
- `requested_at`
- `generated_at`
- `status`
- `evidence_refs`
- `limitations`
- `next_actions`

Component-specific source fields:

- SBM: risk class, risk measure, bucket, risk factor, tenor, sensitivity,
  amount currency, scenario values, source line.
- DRC: issuer, bucket, credit quality, seniority, long/short, gross JTD, net JTD,
  LGD, hedge benefit, defaulted flag.
- RRAO: instrument ID, residual category, base amount, add-on rate,
  classification reason, exclusion state.
- IMA: desk ID, ES term, liquidity horizon, stress period, PLA metrics,
  backtesting metrics, RFET observations, NMRF classification, SES amount.
- CVA: counterparty, netting set, method, EAD, hedge eligibility, spread bucket,
  exposure date, profile state.

UX detail:

- Source lineage must be visible enough for trust but not dominate the first
  screen.
- Every aggregate row needs a source coverage summary: source count, reconciled
  count, missing count, stale count, unsupported count.
- Source-row drilldowns should inherit all active state: run, baseline, scope,
  framework, scenario, mode, filters, selected object.
- Raw rows should be paged, exportable, and explicitly labelled as sample,
  bounded page, or complete result.
- Keep streamlined: the normal user path is aggregate -> driver -> evidence ->
  source row, not direct raw-source browsing.

## 9. Interaction State Model

The app should be driven by one explicit state object. The canonical state
contract is `NAVIGATOR_STATE_AND_ROUTING.md`; this UX contract describes intent
and must not maintain a divergent field list.

High-level reset intent:

The exact reset matrix is owned by `NAVIGATOR_STATE_AND_ROUTING.md`. UX behavior
should follow three principles: preserve valid context where possible, clear
evidence panels as soon as their selected object or resolved evidence target is
stale, and restore to the first useful row/object when the previous selection no
longer exists.

URL contract:

Shareable analytical state must be reflected in the URL according to
`NAVIGATOR_STATE_AND_ROUTING.md`:

```text
/navigator/:runId?scope=book-rates-fixture&baseline=prev-month&mode=capital&view=framework&framework=SA&scenario=High&row=sa-sbm-girr-delta
```

This makes findings shareable between risk, finance, and model teams.

## 10. Visual and Interaction Principles

The UI should feel like a Bloomberg/Workbench-grade analytical tool, not a
consumer analytics dashboard.

Principles:

- Data density, but not cramped noise.
- Fewer panels, stronger relationships.
- Selection should be obvious and reversible.
- Controls should be close to the data they affect.
- Labels should use risk-manager vocabulary, not backend implementation names.
- No decorative cards inside cards.
- Large numbers are useful only when they answer a question.
- Every placeholder is a liability; hide it or label why it is unavailable.
- Loading should preserve layout and show which query is refreshing.
- Keyboard paths must support repeated daily analysis.

Color:

- Neutral canvas and panels.
- One primary selection accent.
- Reserved semantic colors: increase/decrease, warning, error, no-data.
- Do not use a rainbow component palette.

Typography:

- Utility sans for labels.
- Monospace/tabular numerals for amounts.
- Avoid oversized type inside operational surfaces.

Motion:

- Only use motion for collapse/expand, loading, and row selection.
- No ambient animation.

Screen anatomy rule:

- One header.
- One compact scope/breadcrumb region.
- One capital/status strip.
- One primary grid or matrix.
- One inspector.
- Optional explanation drawer.

If a proposed feature needs a second permanent side panel, second KPI band, or
another always-visible table, it probably belongs in a mode, drawer, tab, or
drilldown instead. The product should feel like changing analytical lenses over
the same evidence, not navigating a collection of unrelated dashboards.

## 11. Incremental Implementation Plan

### Slice 1: Navigation Rail Ergonomics

Goal: make hierarchy navigation stop dominating the screen.

Deliver:

- Collapse/expand rail.
- Compact state with selected-scope breadcrumb in header.
- Persistent width/collapse setting in local storage.
- Separate hierarchy search.
- Basic keyboard tree navigation.

Acceptance:

- User can collapse rail and still see active scope.
- Selecting scope updates KPIs/grid/inspector.
- Rail does not consume more than a narrow fixed width in compact mode.

### Slice 2: Selection State Cleanup

Goal: remove drift between scope, framework, scenario, row, and inspector.

Deliver:

- Single `NavigatorState`.
- Explicit reset rules.
- URL query parameters for core state.
- Test state transitions.

Acceptance:

- Changing scope/framework/scenario never leaves inspector showing stale row.
- Reloading a shared URL restores the same analytical view.

### Slice 3: Honest Controls and No-Data States

Goal: remove fake functionality.

Deliver:

- Hide baseline selector until baseline data exists.
- Replace disabled run selector with plain run label unless multiple runs exist.
- Clarify search scope.
- Add no-data reason taxonomy.

Acceptance:

- Every visible control either works or explains why it is unavailable.

### Slice 4: Movement Analysis MVP

Goal: make the app answer "what changed?"

Deliver:

- Add baseline run fixture.
- Add movement columns to grid.
- Add movement summary in capital stack.
- Add top movers mode.

Acceptance:

- User can rank movements by amount and percentage.
- Inspector shows current, baseline, and movement evidence for selected row.

### Slice 5: Inspector Redesign

Goal: make evidence review decisive.

Deliver:

- Inspector summary strip.
- Attribution/source/model/diagnostic tabs with materiality ordering.
- Row-specific source filtering for all components.
- Copyable finding summary.

Acceptance:

- For a selected DRC bucket, only that bucket's source rows appear.
- For an IMA desk, PLA/backtesting/NMRF evidence is visible without JSON diving.

### Slice 6: Component-Specific Deep Dives

Goal: support real risk-manager investigation by component.

Deliver:

- SBM risk-factor drilldown.
- DRC issuer drilldown.
- RRAO classification review view.
- IMA model-evidence view.
- CVA counterparty/no-data view.

Acceptance:

- Each component has at least one natural drill path from component total to
  source row.

### Slice 7: Production Query Readiness

Goal: prepare the UI for result-store/OLAP data.

Deliver:

- Bounded paging for source rows.
- Query cancellation and stale-response guards.
- Server-side sort/filter contract.
- Entitlement and data-completeness placeholders.

Acceptance:

- UI contract does not require loading raw detail datasets into browser memory.

### Slice 8: Governed AI Explanation

Goal: let users request prose analysis from a specialised FRTB explanation agent
without weakening auditability or source discipline.

Deliver:

- `Explain this view` and `Explain selected row` actions.
- Server-side explanation endpoint with prompt template ID and input snapshot
  hash.
- Structured explanation response with findings, evidence references,
  limitations, confidence, and next actions.
- Inspector drawer/tab rendering with clickable evidence references.
- Audit log for requestor, timestamp, model, prompt template, input hash, and
  output hash.

Acceptance:

- Explanation for a DRC bucket cites only that bucket's evidence rows.
- Explanation for an RFET/NMRF risk factor links risk-factor evidence, book/desk
  usage, and SES contribution.
- Explanation for a PLA desk links PLA/backtesting evidence to eligibility and
  capital consequence.
- If baseline, source rows, or RFET evidence are unavailable, the answer states
  that limitation before any interpretation.
- The same unchanged view snapshot reuses the same cached explanation unless the
  user explicitly regenerates.

### Slice 9: Pivot, Hierarchy Aggregation, and Time-Series Drivers

Goal: let risk managers reshape capital, model-evidence, and risk-factor views
without losing reconciliation or lineage.

Deliver:

- Pivot row/column state for hierarchy, component, risk class, desk, book,
  issuer/counterparty, risk factor, scenario, model state, and data state.
- Collapsible hierarchy aggregation with parent subtotals, child counts, warning
  counts, and mixed-state badges.
- Time-window selector for previous run, previous business day, month-end,
  quarter-end, year-on-year, and custom baseline.
- Risk-factor driver view with value history, sensitivity/exposure proxy,
  capital contribution, RFET observation state, and SES movement.
- URL/share-state support for pivot layout, filters, selected object, and time
  window.

Acceptance:

- Collapsing a desk node shows a reconciled subtotal and does not lose warnings
  from child books.
- Filtering to a legal entity or desk subtree changes capital, RFET/NMRF, PLA,
  and source evidence consistently.
- Selecting a risk-factor outlier links to books/desks using it and capital rows
  it affects.
- Pivoted sign-off totals come from backend/result-store aggregates, not
  browser-only arithmetic.

## 12. Near-Term Design Target

The next user-visible milestone should feel like this:

1. The user opens a run and sees one clean capital stack.
2. The hierarchy rail is collapsed by default but discoverable.
3. The breadcrumb reads: `Top of house / LE-DEMO / FICC / Rates / Book`.
4. The grid shows SA stack rows with current, baseline, movement, and status.
5. Clicking `DRC / Corporate` opens an inspector with only Corporate DRC source
   rows.
6. Changing scenario from Binding to High visibly changes SBM and SA amounts.
7. Switching to a residual-risk book hides irrelevant SBM/DRC rows and explains
   why IMA/CVA are not available.
8. A senior risk manager can state: "Capital is up because DRC Corporate moved,
   driven by these issuers/source rows; the movement is in this legal entity and
   book; the data is complete/synthetic/partial."

That is the product standard. Everything else is secondary.

## 13. Source Notes

- BIS Basel Committee, "Minimum capital requirements for market risk", January
  2019: https://www.bis.org/bcbs/publ/d457.htm
- BIS Basel Committee, "The market risk framework - in brief", January 2019:
  https://www.bis.org/bcbs/publ/d457_inbrief.pdf
- BIS Basel Committee, BCBS d457 full standard:
  https://www.bis.org/bcbs/publ/d457.pdf
- OpenAI API docs, Responses API and structured outputs:
  https://developers.openai.com/api/docs/guides/migrate-to-responses and
  https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI API docs, Agents SDK and guardrails:
  https://developers.openai.com/api/docs/guides/agents and
  https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
