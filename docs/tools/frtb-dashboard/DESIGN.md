# FRTB Capital Navigator Viewer — v2 design

This document records the second-attempt design for `tools/frtb_dashboard`. It
supersedes the first-pass P0 dashboard architecture.

Target Navigator contracts:

- UX contract:
  [`UX_AUDIT_AND_INTERACTION_CONTRACT.md`](UX_AUDIT_AND_INTERACTION_CONTRACT.md)
- Mode wireframes:
  [`MODE_WIREFRAMES.md`](MODE_WIREFRAMES.md)
- State and routing:
  [`NAVIGATOR_STATE_AND_ROUTING.md`](NAVIGATOR_STATE_AND_ROUTING.md)
- Capital and movement semantics:
  [`CAPITAL_AND_MOVEMENT_SEMANTICS.md`](CAPITAL_AND_MOVEMENT_SEMANTICS.md)
- Result-store data contract:
  [`RESULT_STORE_DATA_CONTRACT.md`](RESULT_STORE_DATA_CONTRACT.md)

## Design law

Every fact appears once, at the altitude where it belongs:

| Altitude | Zone | Responsibility |
| --- | --- | --- |
| Firm/run | Command ribbon | Run, baseline, binding top-of-house, SA, IMA, CVA state |
| Slice/context | Context bar | Framework, grouping, SBM scenario, regime |
| Aggregation | Blotter grid | Navigation, grouped measures, selected row |
| Line/audit | Inspector | Attribution rows, source rows, diagnostics, framework extras |

The UI is read-only. Regulatory calculations are performed by package fixtures
or, in the target architecture, by upstream capital engines and OLAP stores. The
frontend maps, slices, displays, filters, and requests detail rows; it does not
recalculate capital.

## Visual system

- Light high-density palette: near-white canvas, white panels, hairline borders.
- Monospace numeric cells, 24px grid rows, 44px ribbon, 32px context bar.
- One blue selection accent; muted emerald/crimson only for signed variance.
- No hero cards, marketing gradients, shadowed tiles, rounded pills, or repeated
  total-capital displays.

## v2 scope

Built in v2:

- Firm totals for SA and IMA, with demo output-floor display
  `max(IMA, 0.725 * SA)` computed in the backend from available run totals. The
  multiplier is a non-regulatory demo value chosen to match the current
  `frtb-orchestration` scope-view default; production views should consume the
  resolved floor multiplier from result-store or orchestration payloads.
- Framework segmented control for SA, IMA, and CVA, with CVA rendered as an
  explicit no-data state when absent.
- Fixture-backed business hierarchy metadata for top-of-house, legal entity,
  division, business line, desk, Volcker desk, and book scopes.
- Fixture-backed aggregate blotter endpoint: `GET /api/runs/{run_id}/grid`.
- Fixture-backed line/audit inspector endpoint:
  `GET /api/runs/{run_id}/inspector?row_id=...`.
- SBM scenario columns for base/high/low/binding where package result objects
  expose scenario totals.
- DRC bucket rows and RRAO evidence rows from package result objects.
- IMA IMCC, SES, PLA, backtesting, multiplier, and attribution rows from the
  capital-run fixture and `DeskAuditRecord`.
- Clear no-data diagnostics for baseline variance, CVA, RFET real-price counts,
  ES liquidity-horizon matrices, PLAT UPL histograms, and gross JTD/LGD detail
  where the fixture does not expose those data.

Not built in v2:

- Real S3/HDFS scans, authenticated entitlements, or production AG Grid SSRM.
- Baseline comparison against a second reporting run.
- Per-trade CRIF, RFET, PLAT UPL, or CVA datasets not present in the fixture.

## Backend contract

The v2 backend keeps the same conceptual contract as the target OLAP system:

- Aggregate layer: `GET /api/runs/{run_id}/grid?framework=SA&scenario=Binding`.
- Detail layer: `GET /api/runs/{run_id}/inspector?row_id=sa-drc-corporate`.
- Metadata layer: `GET /api/runs/{run_id}/metadata`.

Aggregate and detail requests accept `hierarchyNodeId` so the same row contract
can be evaluated at top-of-house, legal-entity, division, desk, Volcker-desk, or
book scope. The fixture uses synthetic component membership to make scoped
totals visible: rates nodes contain IMA/SBM, credit nodes contain DRC, and
residual-risk nodes contain RRAO.

Hierarchy node lists, source-row mappings, scoped aggregate totals, and
aggregate/detail reconciliation are backend/result-store contracts. The
frontend may request and render them, but must not derive parent-child
membership, fabricate missing source rows, or recalculate capital totals in the
browser. See [`../../HIERARCHY_OWNERSHIP.md`](../../HIERARCHY_OWNERSHIP.md).

The fixture implementation is intentionally thin. Later DuckDB/ClickHouse/Impala
work should replace the data source behind those endpoints rather than rewrite
the UI.

## Target architecture roadmap

- Partitioned Parquet/ORC in S3 or HDFS by reporting date, framework, entity,
  desk, and book.
- OLAP execution through DuckDB, ClickHouse, or Impala over pre-calculated
  records and daily summary tables.
- API middleware that compiles a safe JSON query contract into parameterized SQL,
  appends entitlement filters, and returns bounded aggregate/detail payloads.
- AG Grid Enterprise server-side row model for production-scale aggregation and
  virtualized audit rows once the licensed dependency and production backend are
  available.
- Inspector pagination with 100-row blocks for raw sensitivity or P&L vectors.

## Guardrails

- Synthetic/demo data is labelled as synthetic.
- Missing data is rendered as `n/a` or a no-data diagnostic, never silently zeroed.
- Unsupported or residual attribution statuses stay visible in the inspector.
- U.S. NPR 2.0 and Basel references are prototype/comparison material, not final
  regulatory capital outputs.
