# Artifact Metadata Ownership

Time-series, shock, scenario-vector, and surface metadata is governed evidence
for completed FRTB runs. It is not a market-data platform and it is not capital
calculation logic. This page is the suite-level ownership contract for agents
adding storage, propagation, orchestration, or Navigator behavior for those
artifact families.

## Ownership Matrix

| Layer | Owns | Must not own |
| --- | --- | --- |
| `frtb-common` | Stable value primitives: `TimeSeriesId`, `ScenarioVectorId`, `ShockId`, `ShockDirection`, `SurfaceId`, `SurfacePointId`, `SurfaceAxisName`, and validated surface coordinates. | Market-data lookup, shock generation, surface interpolation, regulatory classification, or persisted artifact payloads. |
| Component packages (`frtb-ima`, `frtb-sbm`, `frtb-drc`, `frtb-rrao`, `frtb-cva`) | Calculation-ready arrays/scalars and preservation of supplied artifact IDs, source row IDs, mapping versions, and provenance on public result or audit records. | Importing `frtb_result_store`, fetching stored artifacts, sourcing market data, synthesizing missing UPL/CRIF/stress data, generating shocks, or inferring surface axes inside kernels. |
| `frtb-result-store` | Canonical persisted artifact refs, schemas, synthetic fixture artifacts, semantic partition values, mapping versions, lineage, availability states, bounded page reads, and metadata APIs. | Capital formulae, component-owned regulatory semantics, market-data sourcing, pricing, shock calibration, or surface interpolation. |
| `frtb-orchestration` | Suite evidence views over already resolved artifact IDs and component outputs, including explicit `NO_DATA` and `UNSUPPORTED` states. | Result-store lookup, raw artifact reads, artifact semantic inference, or mutation of component capital results. |
| Navigator/backend adapter | Read-only view models over result-store APIs and orchestration evidence, row-linked timeline/shock/scenario/surface panes, cache keys, request cancellation, and explicit no-data UI states. | Browser direct Parquet/S3 reads, client-side RFET/PLA/backtesting/shock/surface classification, capital recomputation, or fabricated rows for missing datasets. |

## Dissemination Flow

1. Upstream systems or fixtures produce calculation-ready inputs plus stable
   artifact identifiers, source row IDs, and mapping versions.
2. Component packages consume the numeric inputs and preserve the supplied
   artifact metadata in result/audit structures without changing capital
   numbers.
3. Orchestration may compose resolved evidence references across components
   when it already has those IDs in its inputs.
4. Result-store commits the canonical artifact refs, schema fingerprints,
   availability state, lineage, and paged payloads for one immutable `run_id`.
5. Navigator loads the committed run, selected row lineage, artifact catalog,
   and bounded detail pages from backend/result-store APIs.

The selected run, hierarchy node, row, artifact ID, semantic partition ID,
framework, scenario, and page filters are part of the cache key. Changing any
of them must cancel stale requests rather than reuse data from another
selection.

## Validation Contract

Tests and CI checks should protect these invariants:

- artifact IDs are unique within a run for the same semantic partition;
- unavailable artifacts carry `NO_DATA` or `UNSUPPORTED` with a reason and no
  fabricated rows;
- shock definitions preserve valid direction/type and branch provenance;
- surface metadata preserves distinct axis names and coordinate tuples;
- scenario-vector and time-series pages preserve source row IDs and mapping
  versions;
- lineage rejects orphan artifact references;
- component packages and orchestration do not import `frtb_result_store` for
  artifact lookup;
- Navigator routes missing UPL, CRIF, stress-vector, and full-surface datasets
  to explicit no-data or unsupported states.

Authoritative implementation details live in
[`docs/modules/frtb-result-store/ARTIFACT_METADATA.md`](modules/frtb-result-store/ARTIFACT_METADATA.md)
and the Navigator adapter contract in
[`docs/modules/frtb-navigator/RESULT_STORE_DATA_CONTRACT.md`](modules/frtb-navigator/RESULT_STORE_DATA_CONTRACT.md).
Risk-factor-specific metadata ownership remains documented in
[`RISK_FACTOR_METADATA_OWNERSHIP.md`](RISK_FACTOR_METADATA_OWNERSHIP.md).
