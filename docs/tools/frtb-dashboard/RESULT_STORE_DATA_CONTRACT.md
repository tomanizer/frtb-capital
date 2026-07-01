# Capital Navigator result-store data contract

This contract defines how the Capital Navigator consumes `frtb-result-store`
data for dashboard view models, audit drilldowns, artifacts, and no-data states.
It is a browser and adapter contract over committed result-store evidence. It
does not replace the package-level result-store documentation.

Authoritative result-store references:

- [`PUBLIC_API.md`](../../modules/frtb-result-store/PUBLIC_API.md)
- [`CAPITAL_NAVIGATOR_METADATA_CONTRACT.md`](../../modules/frtb-result-store/CAPITAL_NAVIGATOR_METADATA_CONTRACT.md)
- [`ARTIFACT_METADATA.md`](../../modules/frtb-result-store/ARTIFACT_METADATA.md)
- [`STORAGE_CONTRACT.md`](../../modules/frtb-result-store/STORAGE_CONTRACT.md)

Companion Navigator contracts:

- [`CAPITAL_AND_MOVEMENT_SEMANTICS.md`](CAPITAL_AND_MOVEMENT_SEMANTICS.md)
- [`IMPLEMENTATION_SLICES.md`](IMPLEMENTATION_SLICES.md)
- [`MODE_WIREFRAMES.md`](MODE_WIREFRAMES.md)
- [`NAVIGATOR_STATE_AND_ROUTING.md`](NAVIGATOR_STATE_AND_ROUTING.md)
- [`UX_AUDIT_AND_INTERACTION_CONTRACT.md`](UX_AUDIT_AND_INTERACTION_CONTRACT.md)

The browser must not recalculate capital, official subtotals, attribution,
RFET/SES, PLA status, or source-row totals. It may sort, filter, format, select,
expand, and compose view models from result-store payloads. Any analytical
number displayed as capital, attribution, movement, eligibility, RFET, SES, PLA,
or source-row count must come from `frtb-result-store` or be clearly rendered as
unavailable.

## Boundary

### Result-store responsibilities

`frtb-result-store` owns committed run evidence and read models:

- run identity, run groups, lifecycle status, and event payloads;
- capital tree nodes, edges, scalar measures, lineage, and attribution records;
- dashboard marts and component-specific read models;
- movement explanation rows and movement summary rows;
- organisation hierarchy snapshots, aggregate rows, and paged source-row
  samples where implemented;
- artifact references, artifact availability states, deterministic pages, and
  local download or object-store URI handoff;
- typed metadata artifact routes for time series, shocks, scenario vectors, and
  surface slices;
- explicit `AVAILABLE`, `NO_DATA`, and `UNSUPPORTED` states.

The store may serve these payloads through the optional FastAPI app or through
package APIs. Physical DuckDB or Parquet table names are not the dashboard
contract.

### Dashboard adapter responsibilities

The dashboard adapter is a thin composition layer. It may:

- choose the active run or run group;
- call result-store endpoints and package APIs;
- merge capital tree, measures, lineage, attribution, marts, and artifact refs
  into stable view models;
- map result-store availability states into UI states;
- preserve result-store IDs in URLs, row keys, cache keys, and evidence links;
- apply display filters and pagination parameters accepted by result-store APIs;
- abort stale in-flight requests when run, node, artifact, filter, or page state
  changes.

The adapter must not:

- compute or restate official capital totals or subtotals;
- infer missing attribution, RFET/SES, PLA, backtesting, or eligibility status;
- add dashboard-local regulatory semantics to source rows;
- query raw SQL or DuckDB table names as the public app contract;
- fetch Parquet or object-store files directly from the browser.

## View-Model Mapping

| Navigator mode | Existing result-store surfaces | Adapter composition | Missing or future capability |
| --- | --- | --- | --- |
| Run selector | `GET /runs`, `GET /runs/{run_id}`, `GET /run-groups`, `GET /run-groups/{run_group_id}/regime-comparison`; `capital_summary`, `component_breakdown`, `regime_comparison` marts | Select one committed `run_id` or comparison `run_group_id`; show lifecycle and suggested status from store payloads | Broader lifecycle workflow remains out of scope for the dashboard |
| Capital tree workbench | `GET /runs/{run_id}/capital-tree`, `GET /runs/{run_id}/nodes/{node_id}`, `GET /runs/{run_id}/nodes/{node_id}/children`, `GET /runs/{run_id}/nodes/{node_id}/measures`; `capital_tree` mart | Build the expandable tree from persisted nodes and edges; attach scalar measures by `node_id`; keep `regulatory_rule_id` as evidence text | Server-side pivot/subtotal query contract is tracked by #1103 |
| Node drilldown inspector | `GET /runs/{run_id}/nodes/{node_id}/measures`, `GET /runs/{run_id}/nodes/{node_id}/attribution`, `GET /runs/{run_id}/nodes/{node_id}/lineage`; `top_contributors`, `residual_attribution`, `unsupported_attribution` marts | Render measures, attribution method, residual amount, unsupported reason, source level, source id, and linked artifacts | RFET/NMRF/SES evidence mart is tracked by #1101 |
| Attribution and contributors | `GET /runs/{run_id}/top-contributors`, `GET /runs/{run_id}/attribution/residual`, `GET /runs/{run_id}/attribution/unsupported`, `GET /runs/{run_id}/nodes/{node_id}/attribution` | Use result-store rankings and persisted attribution ids; distinguish analytical, standalone, residual, and unsupported methods without recomputing them | Additional explanation snapshots are tracked by #1104 |
| Movement analysis | `GET /runs/{run_id}/movements`; `movement_summary` mart | Display persisted baseline run, movement id, node id, driver, from/to/delta amounts, attribution method, and linked artifact | Additional movement classification belongs in result-store, not the browser |
| Organisation hierarchy | `GET /runs/{run_id}/org-hierarchy`, `GET /runs/{run_id}/org-hierarchy/nodes/{node_id}/children`, `GET /runs/{run_id}/org-hierarchy/nodes/{node_id}/aggregate`, `GET /runs/{run_id}/org-hierarchy/nodes/{node_id}/source-rows` | Show hierarchy nodes and children, selected-node aggregate, and source-row sample pages; preserve `status`, `message`, `component_filter`, `offset`, and `next_offset` | Production hierarchy and regime assignment expansion remains under the #1105 epic |
| Artifact drillthrough | `GET /runs/{run_id}/artifacts`, `GET /runs/{run_id}/artifacts/{artifact_id}/page`, `GET /runs/{run_id}/artifacts/{artifact_id}/download` | Page bounded artifact rows with accepted columns, equality filters, limit, and offset; use download only through the result-store route | Browser direct Parquet/S3 reads are forbidden |
| Metadata inspectors | `GET /runs/{run_id}/time-series`, `GET /runs/{run_id}/time-series/{time_series_id}/points`, `GET /runs/{run_id}/shocks`, `GET /runs/{run_id}/shocks/{shock_id}`, `GET /runs/{run_id}/scenario-vectors`, `GET /runs/{run_id}/scenario-vectors/{scenario_set_id}/{scenario_vector_id}/metadata`, `GET /runs/{run_id}/surfaces`, `GET /runs/{run_id}/surfaces/{surface_id}/slice` | Use metadata catalogs for selectors and badges; use node lineage to decide which metadata tabs appear | Timeline/shock/scenario/surface fixture and API hardening is tracked by #1074 and #1075 |
| Component summaries | `component_breakdown`, `ima_desk_dashboard`, `sbm_bucket_ladder`, `drc_issuer_contributors`, `cva_counterparty_contributors`, `rrao_exposure_summary` marts | Build component panels and focused tables from read-model rows; link `node_id` and `artifact_id` back to tree and artifact pages | New dimensions or measures require result-store mart/API changes |
| PLA and backtesting | Current run, desk, event, artifact, and metadata surfaces only where evidence exists | Render only persisted evidence; otherwise show no-data or unsupported state | PLA/backtesting desk eligibility mart is tracked by #1102 |
| Pivot analysis | Existing marts and artifact pages may support fixed dashboard tables | Do not create official subtotal semantics client-side | Server-side pivot aggregate query contract is tracked by #1103 |
| Governed AI explanations | Stable evidence references from runs, nodes, artifacts, attribution, movements, and input snapshot hashes | The adapter may pass bounded evidence references to an explanation viewer when result-store provides a snapshot | Snapshot builder is tracked by #1104 |

## Existing Marts

The following result-store marts are dashboard read models. They are stable
semantic surfaces, not permission for the browser to query raw tables.

| Mart | Purpose | Stable join keys |
| --- | --- | --- |
| `capital_summary` | One summary row per committed run, including total capital and lifecycle fields | `run_id` |
| `capital_tree` | Flattened capital tree for dashboard drilldown | `run_id`, `node_id`, `parent_node_id` |
| `component_breakdown` | Component-level capital totals and counts | `run_id`, `component` |
| `top_contributors` | Ranked persisted attribution contributors | `run_id`, `node_id`, `attribution_id`, `source_id`, `artifact_id` |
| `residual_attribution` | Residual attribution rows and unreconciled branches | `run_id`, `node_id`, `attribution_id`, `target_id`, `artifact_id` |
| `unsupported_attribution` | Unsupported attribution rows with reason text | `run_id`, `node_id`, `attribution_id`, `unsupported_reason`, `artifact_id` |
| `movement_summary` | Baseline-to-current movement summary rows | `run_id`, `baseline_run_id`, `movement_id`, `node_id`, `artifact_id` |
| `ima_desk_dashboard` | IMA desk-level capital, portfolio, book, and node counts | `run_id`, `desk_id` |
| `sbm_bucket_ladder` | SBM risk-class/bucket ladder | `run_id`, `risk_class`, `bucket` |
| `drc_issuer_contributors` | DRC issuer contribution rows | `run_id`, `issuer_id`, `node_id`, `artifact_id` |
| `cva_counterparty_contributors` | CVA counterparty contribution rows | `run_id`, `counterparty_id`, `node_id`, `artifact_id` |
| `rrao_exposure_summary` | RRAO exposure-class summary rows | `run_id`, `node_id`, `exposure_class`, `artifact_id` |

`regime_comparison` is also available for run-group comparison screens and
should be consumed with `/run-groups/{run_group_id}/regime-comparison`.

## Stable ID Rules

The adapter must preserve result-store identifiers verbatim:

- `run_id` and `run_group_id` for route state, cache keys, and comparison
  context;
- `node_id` and `parent_node_id` for tree expansion, selected rows, measures,
  attribution, lineage, movements, and hierarchy-linked views;
- `measure_name` and `currency` for scalar measure display;
- `attribution_id`, `target_type`, `target_id`, `source_level`, `source_id`,
  and `bucket_key` for contribution rows and evidence references;
- `artifact_id`, `artifact_type`, `artifact_status`, `status_reason`,
  `navigator_role`, `schema_id`, `partition_keys`, and `partition_values` for
  artifact navigation;
- semantic artifact partition ids such as `time_series_id`, `shock_id`,
  `scenario_set_id`, `scenario_vector_id`, and `surface_id` for metadata
  detail routes;
- `movement_id`, `baseline_run_id`, `driver_type`, and `driver_id` for movement
  explanations;
- organisation `hierarchy_id`, `version_id`, and hierarchy `node_id` for
  hierarchy views;
- component-specific IDs such as `desk_id`, `book_id`, `portfolio_id`,
  `risk_class`, `bucket`, `issuer_id`, `counterparty_id`, and
  `exposure_class`.

Display labels may be derived from persisted labels or stable IDs. They must
not replace IDs as row keys or evidence references.

## Artifact Paging and Filters

Artifact rows are served through bounded result-store pages:

```text
GET /runs/{run_id}/artifacts/{artifact_id}/page?columns=...&filter=column=value&limit=100&offset=0
```

Rules:

- `limit` and `offset` are result-store paging controls; the browser must not
  request unbounded artifact frames.
- `columns` may select a display subset, but unknown columns are a store error
  and should be shown as an invalid dashboard request.
- `filter` uses simple equality in `column=value` form and may be repeated.
- Source-row samples from organisation hierarchy use their own `limit`,
  `offset`, `total_row_count`, and `next_offset` contract; do not merge those
  counters with artifact page counters.
- Detail payloads expose committed `row_count`, query `filtered_row_count`,
  page `returned`, `next_offset`, and `rows`. A filtered page with fewer rows
  than the committed artifact count is expected.
- Downloads must use
  `GET /runs/{run_id}/artifacts/{artifact_id}/download`. A local artifact may
  return a Parquet file response; an object-store-backed artifact may return
  `mode=s3_uri_handoff`; unavailable artifacts return
  `mode=artifact_unavailable`.

The browser may provide export affordances only for the result-store download
route. It must not construct object-store URLs or local file paths.

## Availability and State Handling

The adapter must render these states explicitly:

| State | Source | UI contract |
| --- | --- | --- |
| Available | `artifact_status=AVAILABLE`, ordinary API rows, or `status=OK` | Render the returned rows and counters |
| No data | `artifact_status=NO_DATA`, `status=NO_DATA`, empty result-store read model, or an explicit no-data payload | Render an honest no-data state; do not synthesize rows |
| Unsupported | `artifact_status=UNSUPPORTED`, `status=UNSUPPORTED`, `method=UNSUPPORTED`, or `unsupported_reason` | Render a capability boundary with the persisted reason |
| Residual | `method=RESIDUAL` or non-zero `residual` | Render residual as stored; do not allocate it across children |
| Stale | A persisted status or event marks stale evidence | Render stale state from the store; do not infer freshness from local time |
| Synthetic | Fixture or metadata fields identify synthetic evidence | Label fixture evidence as synthetic development data |
| Partial | Store payload contains partial counts, filters, page state, or event warnings | Preserve counters and warnings; do not reconcile client-side by summing visible rows |

Unavailable metadata refs can still carry semantic `partition_values`. For
example, a no-data UPL time series may still be addressed by
`time_series_id=ts-plat-upl` and should return `mode=artifact_unavailable`
rather than a client-created empty chart.

## View Composition Flow

For a single-run capital workbench:

1. Load `/runs/{run_id}` and `/runs/{run_id}/events`.
2. Load `/runs/{run_id}/capital-tree` and, where useful, the `capital_tree` and
   `component_breakdown` read models.
3. For the selected `node_id`, load node detail, children, measures,
   attribution, and lineage.
4. Match lineage `source_id` values to artifact refs and metadata catalogs.
5. Render only artifact or metadata tabs linked to the selected node.
6. Page artifact, source-row, and metadata-detail rows from result-store routes.
7. Preserve all IDs in the browser route so refresh, copy-link, and audit
   references resolve to the same run and row.

For run-group comparison:

1. Load `/run-groups` for selector state.
2. Load `/run-groups/{run_group_id}/regime-comparison`.
3. Use returned `runs`, `regime_comparison`, and per-run
   `component_breakdown`.
4. Keep drilldown scoped to a selected `run_id`; do not blend evidence across
   runs unless result-store returns a comparison row.

## Result-Store Gaps Tracked Under #1105

The open result-store epic #1105 owns remaining Navigator-serving gaps. The
dashboard contract treats these as server-side requirements, not adapter work:

- #1074: fixtures and artifact schemas for time series, shocks, scenario
  vectors, surfaces, and source lineage;
- #1075: query APIs for timelines, shock definitions, scenario vectors, and
  surface slices;
- #1101: RFET/NMRF/SES risk-factor evidence mart;
- #1102: PLA/backtesting desk eligibility mart;
- #1103: server-side pivot aggregate query contract with official versus
  display subtotal semantics;
- #1104: governed AI explanation snapshot builder over bounded result-store
  evidence.

Until those capabilities are present for a requested dashboard view, the
adapter must route to explicit no-data, unsupported, or unavailable states. It
must not fill gaps with browser-local calculations.

## Cache and Cancellation Keys

Use stable cache keys that include every result-store identity affecting the
payload:

- run: `run:{run_id}`;
- run group: `run-group:{run_group_id}`;
- capital tree: `run:{run_id}:capital-tree`;
- node detail: `run:{run_id}:node:{node_id}:detail`;
- node children: `run:{run_id}:node:{node_id}:children`;
- node measures: `run:{run_id}:node:{node_id}:measures`;
- node attribution: `run:{run_id}:node:{node_id}:attribution`;
- node lineage: `run:{run_id}:node:{node_id}:lineage`;
- artifact page:
  `run:{run_id}:artifact:{artifact_id}:columns:{columns}:filters:{filters}:offset:{offset}:limit:{limit}`;
- metadata detail:
  `run:{run_id}:metadata:{family}:{semantic-id}:filters:{filters}:offset:{offset}:limit:{limit}`;
- organisation source rows:
  `run:{run_id}:org-node:{node_id}:components:{component_filter}:offset:{offset}:limit:{limit}`.

Changing run, run group, node, artifact, metadata family, semantic id, filter,
component filter, offset, or limit must abort stale in-flight requests.

## Acceptance Checklist

A Navigator implementation conforms to this contract when:

- each major mode maps to result-store API surfaces or an explicit #1105 gap;
- the adapter composes view models without recalculating capital, official
  subtotals, attribution, RFET/SES, PLA status, or source-row totals;
- every interactive row, tab, page, and evidence link preserves the underlying
  stable IDs;
- artifact and source-row pages use result-store paging and counters;
- no-data, unsupported, stale, partial, synthetic, and residual states are
  rendered from persisted state rather than inferred in the browser.
