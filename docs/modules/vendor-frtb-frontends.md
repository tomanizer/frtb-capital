# FRTB SA Frontend Comparison (Vendor Brochures)

## Source PDFs reviewed

- `/Users/thomas/Downloads/FRTB-Standard-Approach-for-Market-Risk-Brochure-_-Oct-20191.pdf` (Bloomberg)
- `/Users/thomas/Downloads/FRTB-SA-Solution-Brochure.pdf` (S&P)
- `/Users/thomas/Downloads/TickSmith_FRTB_White_Paper_Final.pdf` (TickSmith)

For comparison, screenshots were extracted from all PDFs into `/private/tmp/frtb_pdf_pages` and inspected.

## Purpose of this review

The goal is to align how the suite presents FRTB Standardised Approach results in a trader/risk-user workflow.

Key implication: the strongest pattern is not dashboard-first with sparklines, it is a capital-workbench with a dense, auditable hierarchy and strong drill-down controls.

## Vendor UI observations

### Bloomberg FRTB Standardised Approach

- Interface feels like a terminal-style workstation: dense rows, explicit context, stable controls.
- Main capital panel uses a hierarchy that expands from firm level through component buckets.
- Core controls include:
  - position and valuation date,
  - currency and unit selection,
  - scenario selector,
  - flash/status and permission flags,
  - what-if toggle and exception handling entry points.
- A separate operational architecture view shows pipeline steps:
  - position feeds,
  - data mapping/enrichment,
  - analytics,
  - netting and bucketing,
  - capital calculation and attribution,
  - output handoff.
- Drill flow appears to keep users in one place: selecting a higher-level node reveals next-level buckets and risk-factor/tenor detail.

### S&P Global Market Intelligence

- Strong visual decomposition, but still anchored by a capital tree.
- Capital screen combines:
  - hierarchical total / component table,
  - treemap and sunburst/ring decomposition,
  - export tooling.
- Sensitivity screen has explicit risk-class navigation and per-tenor visual breakdown.
- Emphasises:
  - CRIF-shaped sensitivity workflow,
  - secure interface and auditability,
  - configurable local interpretation,
  - scenario what-if for risk weights.

### TickSmith

- Not a capital-workbench itself; mostly a model data-control layer and report portal.
- Valuable patterns for our suite:
  - strict data lineage and report metadata,
  - entitlements and redaction-aware delivery,
  - “accepted / rejected / only modelable” row-level governance,
  - filterable, reproducible exports,
  - pipeline observability and event logs,
  - alert/escalation and monitoring surfaces.
- Architecture diagram reinforces operational expectations:
  - private/vendor ingestion,
  - raw staging + normalization,
  - transformation/join pipelines,
  - modelability and pooled observation outputs,
  - distributed query and orchestration.

## Revisions to how we should present SA data

The combined evidence suggests a two-part UI posture:

1) Keep the capital hierarchy as source of truth.
2) Attach visual decomposition and quality metadata as controlled adjuncts.

### 1) Run header (always visible)

- run id, calculation date, position date
- base currency and unit
- regulation/jurisdiction profile and family
- input + profile hashes
- status, warnings, unsupported-feature count
- validation timestamps and last event age
- exports: JSON, CSV, Parquet/Arrow, audit bundle

### 2) Capital tree first

- Root: Standardised Approach total
- SBM node:
  - GIRR delta, vega, curvature
  - CSR non-security / security
  - FX, equity, commodity where applicable
- DRC node:
  - non-security / security split
- RRAO node:
  - exotic and residual buckets
- Columns should include:
  - SA contribution,
  - % of parent,
  - row status,
  - count and exclusion context,
  - warning/unsupported markers,
  - source/citation references where available.

### 3) Deterministic drill-down workbench

Selecting a row should open consistent tabs:

- rows (attribution-level contributors),
- bucket view,
- risk-factor view,
- warnings,
- excluded/unsupported records,
- citations/source references.

### 4) Visual companion layers (not replacements)

- treemap / sunburst for component mix,
- tenor or risk-factor chart for the selected node,
- waterfall for deltas,
- reconciliation strip that validates table totals.
- Every chart should link back to the underlying table and support export.

### 5) Input quality and control plane

- Show manifest status for each expected input table:
  - supplied / missing / partial,
  - accepted / rejected / excluded row counts,
  - adapter diagnostics and hash comparison,
  - expected validation tasks and failures.
- Entitlements model should remain visible at output and report level.

### 6) What-if + comparison

- Allow run-to-run and profile-to-profile comparisons.
- Show capital deltas with context:
  - scenario/risk-weight deltas,
  - unsupported-method caveats,
  - impact surfaced at the same tree granularity.

## Implementation intent for this project

For the FRTB suite UI, prioritize:

- audit-first ordering,
- stable IDs and deterministic grouping,
- one-row-per-contribution semantics,
- explicit unsupported/exception records,
- exportability from every major screen,
- reproducible filters and profile metadata in URL or run manifest.

This aligns with existing attribution and governance expectations while matching the “workbench” patterns seen in Bloomberg and S&P and the control-plane depth from TickSmith.
