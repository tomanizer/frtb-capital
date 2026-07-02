# 49. Result evidence and market data platform boundary

Date: 2026-07-01

## Status

Proposed

## Context

Issue #1072 adds first-class result-store contracts for time-series,
shock-definition, scenario-vector, and surface-grid artifacts. Those contracts
make the FRTB Navigator more honest: the UI can discover RFET observation
timelines, PLAT vectors, SBM shock definitions, IMA scenario vectors, and
volatility surfaces as persisted run evidence instead of faking them in the
frontend.

That work creates an important architectural boundary question. The same words
can describe two different systems:

1. **Run-scoped regulatory evidence.** The exact artifact, source row,
   semantic identifier, hash, or unavailable-state needed to explain,
   reproduce, and audit a committed FRTB capital result.
2. **Enterprise market/scenario-data infrastructure.** The sourcing,
   normalization, cleansing, calibration, distribution, and long-term storage
   of prices, curves, surfaces, shocks, real-price observations, and scenario
   histories.

The suite already has related boundaries:

- [ADR 0023](0023-arrow-tabular-handoff-boundary.md) allows Arrow for
  tabular handoff and IO but keeps capital kernels NumPy-native and
  package-owned.
- [ADR 0045](0045-canonical-batch-pipeline-with-adapter-ingress.md) requires
  adapter ingress into package-owned regulatory batches, and forbids
  `frtb-common` from absorbing component-specific regulatory semantics.
- The FRTB Navigator metadata contract defines the new artifact endpoint
  families as a read model: the UI may display persisted metadata but must not
  generate shocks, interpolate surfaces, infer missing classifications, or
  calculate capital.

Without an explicit boundary, `frtb-capital` could drift into a generic
market-data lake, scenario engine, curve/surface calibration service, or RFET
observation collection platform. That would dilute the suite's purpose and
pull non-regulatory operational concerns into capital-kernel review.

Risk-factor identity is the join key across time-series, shocks, scenario
vectors, and surfaces. This ADR treats risk-factor identifiers as run-scoped
evidence references. [ADR 0050](0050-risk-factor-identity-and-package-projection-boundary.md)
defines the suite-wide risk-factor identity and package-projection boundary.

## Decision

`frtb-capital` owns the **regulatory result contract** for completed FRTB runs.
It may persist or reference immutable, run-scoped evidence artifacts when those
artifacts are needed to calculate, reproduce, audit, or explain a committed
capital result.

`frtb-capital` does **not** own the enterprise platform that sources,
cleanses, calibrates, generates, distributes, or warehouses market data,
scenario data, real-price observations, shock libraries, or volatility
surfaces.

The boundary rule is:

```text
If the object is required to explain or reproduce a committed FRTB result,
the suite needs a stable contract, reference, or run-scoped artifact for it.

If the object is required to produce, clean, calibrate, distribute, or
warehouse market/scenario data generally, it belongs outside the suite.
```

## Scope owned by `frtb-capital`

The suite may own the following narrow contracts.

### 1. Stable artifact identities

`frtb-common` may define lightweight identifiers and coordinates that are
package-neutral and audit-stable:

- `TimeSeriesId`;
- `ScenarioId`, `ScenarioSetId`, and `ScenarioVectorId`;
- `ShockId`;
- `SurfaceId` and `SurfacePointId`;
- surface coordinate primitives such as axis name, axis kind, and point
  coordinates.

These objects are identifiers and metadata carriers only. They must not load
market data, calibrate curves, interpolate surfaces, generate shocks, or run
capital formulae.

### 2. Run-scoped evidence artifacts

`frtb-result-store` may persist immutable evidence artifacts or immutable
references to evidence artifacts for a committed run:

- time-series points used by a run, such as RFET observation evidence,
  RTPL/HPL/UPL vectors, backtesting exception histories, or stress-window
  vectors;
- shock definitions or shock-set members applied by a run;
- scenario-vector metadata used by IMA, PLAT, stress-period, or backtesting
  analysis;
- surface-grid points or slices used by a run;
- unavailable artifact refs with explicit `NO_DATA` or `UNSUPPORTED` status
  when a dataset is absent or outside implemented scope.

The result store may expose these artifacts through read-only APIs for the
FRTB Navigator. It may page, filter, serialize, catalogue, and return
availability status for committed artifacts.

Package-owned deterministic regulatory shocks are allowed when they are direct
outputs of cited package logic. For example, SBM may produce curvature up/down
shock evidence for a committed calculation branch. That is different from
owning an enterprise shock-library calibration or scenario-generation service,
which remains outside this repo.

### 3. FRTB-specific derived statuses

The suite may expose FRTB-specific statuses when they are outputs of the
calculation or validation layer for a committed run. Examples include:

- RFET/modellability status when supported by package logic and cited tests;
- PLAT zone, backtesting zone, and supervisory multiplier evidence;
- SBM binding correlation scenario and scenario totals;
- IMA scenario-vector evidence used for ES, SES, PLA, or backtesting views;
- no-data, unsupported, provisional, stale, or failed-validation status for
  run evidence.

These statuses must be persisted or derived by the relevant package/result
store path. The Navigator must not infer regulatory classifications from raw
points on the client.

Ownership is explicit:

| Concept | Owner |
| --- | --- |
| Artifact availability, catalog rows, pagination counters | `frtb-result-store` |
| RFET/modellability evidence and status | `frtb-ima` |
| PLAT, backtesting, exception-ledger, and multiplier evidence | `frtb-ima` |
| SBM correlation scenario totals and binding scenario | `frtb-sbm` |
| SBM deterministic regulatory shock definitions | `frtb-sbm`, persisted as result-store evidence |
| DRC jump-to-default and offsetting evidence | `frtb-drc` |
| RRAO add-on evidence | `frtb-rrao` |
| CVA sensitivity, counterparty, and surface references | `frtb-cva` |
| Surface calibration, interpolation, and market-data lifecycle | external data platform |
| Rendering, filtering, and inspection UX | FRTB Navigator |

`frtb-result-store` owns availability and retrieval. It must not become the
place where RFET, PLAT, SBM, DRC, RRAO, or CVA regulatory classifications are
invented.

### 4. Provenance links from model results to artifacts

Capital-producing packages may carry lightweight provenance fields on result
records or batch inputs:

- referenced `time_series_id`;
- referenced `shock_id` or future `shock_set_id`;
- referenced `scenario_vector_id` or `scenario_set_id`;
- referenced `surface_id` and `surface_point_id`;
- source-system, source-file, source-row, input-hash, or mapping-version
  metadata when needed for audit.

These fields are references to evidence. They must not make package kernels
depend on market-data clients, object stores, data-lake readers, or surface
interpolators.

### 5. Read-only Navigator query contract

The result-store API may provide read-only query shapes that are optimized for
inspection:

- list metadata catalogs for one committed run;
- fetch one paged time-series slice;
- fetch one shock definition or shock-set member page;
- fetch one scenario-vector metadata page;
- fetch one filtered surface slice;
- expose artifact availability and reconciliation counters.

These APIs are not a write path, calibration endpoint, scenario-generation
service, or market-data distribution API.

## Scope explicitly outside `frtb-capital`

The following responsibilities belong to an external market-data,
scenario-data, reference-data, or data-lake platform:

- vendor feed ingestion and normalization;
- golden-source price, curve, volatility, spread, and reference-data
  management;
- real-price observation collection workflows;
- RFQ/trade-observation capture;
- curve and surface calibration;
- surface interpolation and extrapolation services;
- scenario generation, shock calibration, and shock-library lifecycle
  management;
- intraday streaming, Kafka-style distribution, or live market-data
  subscription handling;
- large historical time-series warehousing;
- object-store partition management for enterprise data lakes;
- entitlement-aware data distribution outside the committed result-store
  read model.

External systems may feed the suite by producing immutable files, Arrow
handoffs, object-store URIs, hashes, source-row identifiers, and semantic
artifact IDs. The suite records exactly what a run consumed; it does not become
the upstream system of record.

The suite may store the interpolation policy identifier, quote convention, or
surface-convention metadata used by an upstream system when needed for audit.
It must not implement the interpolation engine or calibration process without a
later ADR that deliberately expands scope.

## Integration model

The intended architecture is:

```text
External market/scenario/reference-data platforms
    -> immutable files, Arrow handoffs, object-store URIs, hashes, semantic IDs
    -> package adapters and typed regulatory batches
    -> capital kernels and frozen audit/result records
    -> frtb-result-store committed run bundle
    -> FRTB Navigator read-only inspection API
```

The suite must keep these layers separate:

| Layer | Owns | Must not own |
| --- | --- | --- |
| External data platform | sourcing, cleansing, calibration, scenario generation, long history | FRTB capital result semantics |
| Package adapters | converting approved handoff data into package-owned batches | market-data lifecycle or generic calibration |
| Capital kernels | cited regulatory formulae over typed arrays/batches | Arrow, dataframes, object-store clients, interpolation services |
| Result store | immutable run outputs, evidence refs, artifact catalogs, read-only pages | live data sourcing or write-side market-data management |
| Navigator | inspection, slicing, drill-down, no-data/unsupported display | regulatory inference or capital calculation |

## Design rules

### Rule 1: evidence is immutable and run-scoped

Evidence artifacts stored by the result store are snapshots of what a committed
run used. They are not mutable golden-source datasets. If an upstream price,
shock, surface, or scenario changes, a new run must reference a new immutable
artifact, hash, version, or URI.

### Rule 2: identifiers are package-neutral; interpretation is package-owned

`frtb-common` may define stable IDs and shape primitives. It must not define
SBM, DRC, RRAO, CVA, or IMA regulatory meaning for those IDs. Package-local
contracts and validators retain component-specific interpretation and citations.

### Rule 3: kernels receive typed inputs, not external data handles

Capital kernels must not receive market-data clients, SQL connections,
object-store paths, dataframe handles, Arrow tables, or mutable artifact
readers. Adapters resolve evidence into typed package-owned batches before
kernel execution.

### Rule 4: unavailable evidence is explicit

The result store must distinguish:

- `AVAILABLE`: rows or references are present for the committed run;
- `NO_DATA`: the run explicitly lacks the dataset;
- `UNSUPPORTED`: the package/profile does not implement the dataset;
- future statuses such as `PROVISIONAL`, `STALE`, or `FAILED_VALIDATION` when
  required by package logic.

The Navigator must render unavailable evidence honestly. It must not convert
missing evidence into zero, synthesize fake rows, or hide unsupported features
when the selected result implies that the user expects them.

### Rule 5: client-side UI does not own regulatory semantics

The FRTB Navigator may display stored metadata, status, source rows, and
audit counters. It must not:

- decide RFET pass/fail status from raw observation points;
- decide PLAT or backtesting zones from raw vectors;
- choose binding SBM correlation scenarios;
- interpolate or extrapolate surfaces;
- generate shock vectors;
- calculate or restate capital outside persisted result-store outputs.

### Rule 6: richer semantics require explicit contracts

Future additions such as shock sets, RFET ledgers, ES liquidity-horizon
matrices, stress-window vectors, UPL spike diagnostics, or surface
interpolation metadata must be added as explicit contracts with tests and
documentation. They must not be smuggled into generic JSON metadata fields when
they affect audit, regulatory interpretation, or UI behavior.

Generic artifact schemas are storage contracts. Regulatory behavior requires a
named semantic profile that declares:

| Required item | Purpose |
| --- | --- |
| Owner package | Identifies where regulatory interpretation lives |
| Artifact family and schema | Identifies the storage/read model |
| Required fields | Prevents optional metadata from becoming hidden logic |
| Validation rules | Defines what the suite checks before commit or display |
| Regulatory citations | Ties derived status to cited package logic |
| Navigator behavior | Defines what the UI may display and what it must not infer |

For example, `common.time_series.v1` can store RFET observations, RTPL, HPL,
UPL, and backtesting histories. Each regulatory use needs its own semantic
profile before it drives status, filtering, warnings, or capital explanation.

## Enforcement

This ADR is enforced through design review, tests, and existing quality gates:

| Rule | Enforcement |
| --- | --- |
| Kernels do not import data clients, dataframes, Arrow tables, or object-store readers | ADR 0023 import-boundary checks and package review |
| Common identifiers stay package-neutral | `frtb-common` tests and review for absence of component-specific semantics |
| Regulatory statuses have package owners | Package-local tests and explicit semantic-profile documentation |
| Result-store APIs are read-only evidence views | API tests for catalog, status, paging, and unavailable-artifact behavior |
| Navigator does not infer regulatory classifications | Frontend tests and review against the metadata contract |
| Generic JSON metadata does not become hidden business logic | ADR review required for new semantic profiles affecting behavior |

Code that violates these rules should be moved to the owning package, an
external data platform, or a new ADR-backed integration boundary.

## Examples

### In scope

- A committed IMA run references `scenario-vector-rtpl` and exposes the exact
  rows used for a PLAT view.
- A committed SBM result references `shock-sbm-curvature-up` and
  `shock-sbm-curvature-down`.
- A CVA sensitivity batch stores `volatility_surface_id` and
  `volatility_surface_point_id` for audit linkage.
- A run exposes `ts-plat-upl` with `artifact_status=NO_DATA`, so the Navigator
  can render a truthful no-data state.
- A profile exposes `surface-cva-full-vol-cube` with
  `artifact_status=UNSUPPORTED`, so the Navigator can render a capability
  boundary.

### Out of scope

- Downloading vendor tick history to build an RFET observation warehouse.
- Calibrating an implied-volatility surface.
- Interpolating a swaption surface point for pricing.
- Generating a historical VaR shock scenario library.
- Serving a generic market-data API to downstream consumers.
- Managing live entitlements for enterprise market-data subscriptions.

## Consequences

**Positive:**

- The FRTB Navigator can inspect richer evidence without faking data or
  growing client-side regulatory logic.
- Capital packages can carry audit references to the inputs they used while
  keeping kernels small, deterministic, and package-owned.
- `frtb-common` gains reusable identity primitives without becoming a
  market-data model.
- `frtb-result-store` remains an immutable run-output store, not a generic
  data lake.
- Future integration with DuckDB, ClickHouse, Impala, S3, HDFS, or enterprise
  market-data services remains possible through adapters and immutable
  references.

**Negative:**

- Some useful workflows require two systems: an upstream market/scenario-data
  platform and this result suite.
- The result store will need explicit read-model contracts for each new
  evidence family instead of accepting arbitrary opaque blobs.
- Package adapters must be clear about when they merely reference upstream
  evidence versus when they validate FRTB-specific semantics.

**Risks to guard against:**

- Recreating a market-data lake inside `packages/frtb-result-store`.
- Letting generic metadata dictionaries become de facto regulatory contracts.
- Letting the Navigator infer classifications that should be package outputs.
- Passing object-store readers, SQL clients, Arrow tables, or interpolation
  services into capital kernels.
- Treating `NO_DATA` as zero capital or `UNSUPPORTED` as an empty dataset.

## Follow-up work

- Add issue-scoped contracts for shock sets, including `shock_set_id`,
  calibration/version metadata, scenario linkage, and affected risk-factor
  membership.
- Add issue-scoped contracts for richer time-series semantics, including
  purpose, observation window, frequency, calendar, data-quality status, and
  valuation timestamp.
- Add issue-scoped contracts for RFET evidence summaries so modellability
  status is produced by package/result-store logic rather than the UI.
- Add issue-scoped contracts for surface convention metadata, including axis
  types, value convention, quote convention, interpolation/extrapolation policy
  references, and stale-point status.
- Add issue-scoped contracts for PLAT/UPL and backtesting evidence so the
  Navigator can show vectors and exception ledgers from persisted outputs.
- Keep enterprise sourcing, calibration, and long-history storage outside this
  repo unless a later ADR intentionally expands the suite scope.

## References

- [ADR 0011](0011-core-runtime-dependency-policy.md): core runtime dependency
  policy.
- [ADR 0012](0012-capital-impact-attribution.md): attribution-ready audit and
  branch metadata.
- [ADR 0023](0023-arrow-tabular-handoff-boundary.md): Arrow tabular handoff
  boundary.
- [ADR 0029](0029-unified-standardised-component-handoff-contract.md): unified
  Standardised Approach component handoff.
- [ADR 0033](0033-arrow-batch-and-component-summary-vocabulary.md): Arrow batch
  and component-summary vocabulary.
- [ADR 0045](0045-canonical-batch-pipeline-with-adapter-ingress.md): canonical
  batch pipeline with adapter ingress.
- [ADR 0050](0050-risk-factor-identity-and-package-projection-boundary.md): risk
  factor identity and package projection boundary.
- [`docs/modules/frtb-result-store/FRTB_NAVIGATOR_METADATA_CONTRACT.md`](../modules/frtb-result-store/FRTB_NAVIGATOR_METADATA_CONTRACT.md):
  FRTB Navigator metadata read-model contract.
- #1072: time-series, shocks, and surface metadata architecture.
