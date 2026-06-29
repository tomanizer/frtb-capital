# FRTB Capital Dashboard — requirements and design

Prototype dashboard for exploring FRTB capital run results across IMA, Standardised
Approach (SBM + DRC + RRAO), and CVA, with attribution drill-down. This document
captures requirements, information architecture, and phased delivery. Outputs shown
are **not final regulatory capital**.

## 1. Problem statement

Client onboarding teams and model owners need a single place to answer:

- What is total capital for this run, and how does it split across IMA, SA, and CVA?
- For an IMA desk: what drives IMCC, SES/NMRF, PLA, backtesting, and the binding charge?
- For SA: how do SBM, DRC, and RRAO compose, and what are the top contributors?
- Where does attribution reconcile, and where is it explicitly unsupported or residual?

Today those answers live in package demos, NDJSON audit logs, notebooks, and (when
committed) the `frtb-result-store`. The dashboard unifies navigation and drill-down
without re-implementing capital math in the UI.

## 2. Users and jobs-to-be-done

| Persona | Primary jobs |
| --- | --- |
| Model owner / quant | Inspect PLA zone, NMRF method selection, ES stress-period choice, IMCC/LHA breakdown for a desk |
| SA lead | Compare SBM/DRC/RRAO subtotals, drill to bucket/issuer/line attribution |
| Model validation | Verify reconciliation status, residual/unsupported records, input hashes |
| Client integration | Tie a run to profile, calculation date, lineage hashes, and component summaries |

## 3. Functional requirements

### 3.1 Run catalogue

- List capital runs with `run_id`, `calculation_date`, `profile_id`, `base_currency`,
  jurisdiction family, and component availability (IMA / SA / CVA).
- Filter by date range, profile, desk, legal entity.
- Show run metadata: `input_hash`, `policy_hash`, package versions, prototype disclaimer.

### 3.2 Top-of-house view

- Suite total when orchestration provides it; otherwise show available components.
- Cards for IMA RC, SA total (`SBM + DRC + RRAO`), and CVA (when present).
- Movement vs prior run (when result-store movements exist).
- Explicit empty states when a component is missing (fail-closed, not zero placeholders).

### 3.3 Capital tree navigation

Mirror `frtb-result-store` capital tree semantics:

- Nodes: `TOTAL` → `IMA` | `SA` | `CVA` → desk / risk class / bucket / line grains.
- Each node exposes: label, amount, `node_type`, citations, reconciliation flags.
- Breadcrumb + sidebar tree; clicking a node opens its detail pane.

### 3.4 IMA desk drill-down

Per desk (from `DeskAuditRecord` or result-store IMA nodes):

| Panel | Content source |
| --- | --- |
| **Summary** | `capital.total`, `models_based_capital`, binding term, eligibility |
| **IMCC** | `imcc` map: unconstrained/constrained LHA ES, risk-class components |
| **SES / NMRF** | `ses` + `nmrf_valuation`: method per RF, stress period per risk class, SES total |
| **PLA** | `pla`: KS statistic, zone, window diagnostics |
| **Backtesting** | `backtesting`: APL/HPL exceptions at 97.5% and 99% |
| **Attribution** | `desk_contributions(record)` → `CapitalContribution` rows with status |

Non-additive NMRF SES and LHA ES must display as **unsupported explain** rows
(ADR 0038), not fake Euler slices.

### 3.5 SA component drill-down

| Component | Summary | Drill grains | Attribution API |
| --- | --- | --- | --- |
| **SBM** | Risk-class capital, measure (delta/vega/curvature) | Bucket, sensitivity | `calculate_sbm_attribution`, grain summaries |
| **DRC** | Category and bucket capital | Issuer, bucket, category | `summarize_drc_attribution_by_*` |
| **RRAO** | Line add-ons by evidence type | Desk, line, evidence type | `calculate_rrao_attribution`, allocation report |

SA composition row shows `compose_standardised_approach_capital` total with
jurisdiction-family guard (ADR 0022).

### 3.6 CVA drill-down

When CVA summary exists:

- BA-CVA vs SA-CVA method split, netting-set standalone lines, sensitivity buckets.
- Attribution via `attribute_cva_capital` / `project_cva_attribution`.
- Unsupported MAR50 branches surfaced explicitly.

### 3.7 Attribution and reconciliation

- Table of contributions: component, category, source level/id, method, amount,
  `reconciliation_status`, reason.
- Filters: reconciled / partial residual / unsupported.
- Top-N contributors (align with result-store `top-contributors`).
- Suite roll-up via `build_suite_attribution_report` when bundles exist.

### 3.8 Lineage and artifacts

- Per node: `input_hash`, `profile_hash`, lineage rows, adapter diagnostics link.
- Large artifacts (scenario P&L vectors, tail evidence): paginated preview via
  result-store artifact endpoints — not loaded eagerly into the browser.

## 4. Non-functional requirements

| Area | Requirement |
| --- | --- |
| Performance | Initial overview < 2s on demo runs; lazy-load drill panels |
| Auditability | Show hashes, citations, reconciliation status on every capital number |
| Safety | Read-only UI; no capital recalculation in the browser |
| Style | Match onboarding mapper: IBM Plex, navy sidebar, step/tree navigation, panel cards |
| Dependencies | FastAPI + React; reuse workspace packages for demo mode; optional result-store backend |

## 5. Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│  React dashboard (tools/frtb_dashboard/frontend)            │
│  Overview │ Capital tree │ Desk/Component detail │ Attr.    │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST /api/*
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI BFF (tools/frtb_dashboard/backend)                 │
│  • DemoRunBuilder — live fixture/demo calculations          │
│  • ResultStoreAdapter — proxy frtb-result-store API (future)│
└───────────────┬─────────────────────────┬─────────────────┘
                │                         │
     frtb-ima / sbm / drc / rrao / cva     frtb-result-store (committed runs)
     frtb-orchestration (SA + suite)        DuckDB/Parquet evidence
```

**Boundary rule:** the dashboard never imports private kernel modules. It consumes
public result objects, audit records, attribution helpers, and `ComponentCapitalSummary`.

## 6. API sketch (dashboard BFF)

| Endpoint | Purpose |
| --- | --- |
| `GET /api/runs` | Run catalogue |
| `GET /api/runs/{id}` | Run header + top-level totals |
| `GET /api/runs/{id}/capital-tree` | Flat/node tree for navigation |
| `GET /api/runs/{id}/nodes/{node_id}` | Node measures + child ids |
| `GET /api/runs/{id}/nodes/{node_id}/attribution` | Attribution rows |
| `GET /api/runs/{id}/ima/desks/{desk_id}` | IMA desk panels (PLA, NMRF, IMCC, …) |
| `GET /api/runs/{id}/sa` | SA composition + component summaries |

Phase 2 adds `?source=result-store&store_root=...` to read committed runs instead
of demo builder.

## 7. UI information architecture

```text
Sidebar                    Main canvas
─────────                  ───────────
Runs                       [Overview KPIs]
 └ demo-suite-001          [Capital tree breadcrumb]
    IMA                    ├─ IMA › Rates Desk
    ├─ Rates Desk          │   PLA │ NMRF │ IMCC │ Backtest │ Attribution
    SA                       └─ SA › DRC › bucket-12
    ├─ SBM
    ├─ DRC
    └─ RRAO
```

**Overview KPIs:** IMA RC, SA total, suite total, profile chip, as-of date.

**Detail tabs (context-sensitive):**

- IMA desk: Summary · IMCC · SES/NMRF · PLA · Backtesting · Attribution
- SA component: Summary · Breakdown · Attribution · Unsupported/Residual
- Any node: Measures · Children · Lineage

## 8. Phased delivery

| Phase | Scope | Data source |
| --- | --- | --- |
| **P0 (MVP)** | Demo run, tree nav, IMA desk panels, SA totals + DRC/SBM/RRAO summaries | Live fixture/demo calculations |
| **P1** | Result-store adapter, run picker over committed Parquet, artifact paging | `frtb-result-store` API |
| **P2** | Movements, regime comparison, impact analysis (baseline vs candidate) | Result-store + package impact APIs |
| **P3** | Multi-desk IMA, firm-level suite capital, export audit pack | Orchestration + store |

## 9. Regulatory and prototype guardrails

- Banner on every screen: prototype outputs, not final regulatory capital.
- Unsupported paths render explicit reasons (never silent zero).
- NMRF/LHA non-additive evidence labeled per IMA attribution policy.
- Citations shown where package results carry them.

## 10. Test strategy

- API tests: demo run builds, tree shape, IMA desk payload keys, attribution row counts.
- Golden hashes optional for demo run totals (fixture-backed).
- Frontend smoke: run list → tree click → desk tab render.

## 11. Relation to existing assets

| Asset | Role |
| --- | --- |
| `frtb-result-store` FastAPI | Long-term read model; dashboard BFF can proxy it |
| `tools/onboarding_mapper` | Visual system and app shell pattern |
| Package `ATTRIBUTION.md` files | Drill-down semantics per component |
| IMA `DeskAuditRecord` / NDJSON | IMA desk evidence shape |
| `compose_standardised_approach_capital` | SA total |
