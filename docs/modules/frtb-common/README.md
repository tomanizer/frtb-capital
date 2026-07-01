# frtb-common

`frtb-common` is the shared foundation package for package-neutral mechanics in
the `frtb-capital` workspace.

## Package Status

- Package directory: `packages/frtb-common`
- Import name: `frtb_common`
- Implementation status: shared primitives
- Validation status: unit-tested shared handoff and CRIF normalization helpers

Current runtime contents are deliberately small and package-neutral:

- package status metadata plus explicit unsupported/unimplemented exception
  types;
- `ComponentCapitalSummary`, `StandardisedComponent`, and
  `ComponentSummaryError` for the SA component-to-orchestration contract
  accepted in
  [ADR 0029](../../decisions/0029-unified-standardised-component-handoff-contract.md);
- Arrow-backed tabular handoff primitives for column declarations,
  null/chunk/dictionary policies, accepted/rejected tables, adapter
  diagnostics, row id checks, deterministic sorting, and content/handoff
  hashes;
- CRIF-to-Arrow normalization for source-column discovery, alias normalization,
  primitive coercion, accepted/rejected partitioning, diagnostics, metadata,
  source hashes, and package-supplied RiskType mapping. The public
  `frtb_common.crif` import path remains stable while the implementation is
  physically split across CRIF type contracts, normalization orchestration, and
  vectorized Arrow static-mapping modules;
- stable artifact identity primitives for time series, scenarios, shocks, and
  surfaces, including two-axis `SurfacePointCoordinates` for persisted surface
  points. These are metadata/provenance objects only; they do not fetch market
  data, interpolate volatility surfaces, generate shocks, or calculate capital;
- `jsonable` serialization for common domain values;
- regulatory citation test helpers for package policy objects.

## Shared Boundary Flow

```mermaid
flowchart LR
  source["Client source rows<br/>CRIF, vendor, or Arrow"]
  common["frtb-common boundary<br/>normalize, validate columns, hash"]
  diagnostics["Accepted / rejected tables<br/>adapter diagnostics"]
  adapter["Package adapter<br/>RiskType and regulatory semantics"]
  kernel["Package-owned NumPy kernel<br/>IMA, SBM, DRC, RRAO, CVA"]
  summary["Neutral handoff<br/>ComponentCapitalSummary or result summary"]
  orchestration["frtb-orchestration<br/>SA and suite aggregation"]

  source --> common
  common --> diagnostics
  common --> adapter
  adapter --> kernel
  kernel --> summary
  summary --> orchestration
```

Capital packages still own RiskType meaning, regulatory validation, typed input
batches, NumPy kernels, audit records, and package-specific policy objects.
`frtb-common` does not encode IMA, SBM, DRC, RRAO, or CVA regulatory semantics.

## Artifact identity primitives

The package-neutral artifact identifiers are deliberately small value objects:

| Primitive | Use |
| --- | --- |
| `TimeSeriesId` | Identifies a persisted observed or calculated timeline. |
| `ScenarioId` | Identifies one scenario observation. |
| `ScenarioSetId` | Identifies an ordered set of scenario observations. |
| `ScenarioVectorId` | Identifies a scenario vector or cube artifact. |
| `ShockId` | Identifies a persisted shock definition. |
| `ShockDirection` | Provides canonical direction labels for persisted shock definitions. |
| `SurfaceId` | Identifies a persisted surface or grid. |
| `SurfacePointId` | Identifies one coordinate point on a persisted surface. |
| `SurfaceAxisName`, `SurfaceCoordinate`, `SurfacePointCoordinates` | Validate two-axis surface coordinates for provenance and read models. |
| `SurfaceAxisKind` | Distinguishes labelled and numeric surface coordinate values. |
| `ArtifactIdentityError` | Reports invalid artifact identifiers or surface coordinates. |

These primitives are suitable for result-store references, package provenance
fields, and Navigator lineage. They are not a market-data model. Risk-factor
identity, RFET vendor mapping, and organisation hierarchy boundaries are
documented separately in ADRs 0050-0052.

`frtb-common` must not import from capital component packages.

`pyarrow` is allowed here only for tabular handoff and CRIF normalization under
[ADR 0023](../../decisions/0023-arrow-tabular-handoff-boundary.md). The
dependency policy in
[ADR 0011](../../decisions/0011-core-runtime-dependency-policy.md) keeps
capital kernels NumPy-native and keeps dataframe libraries outside required
runtime kernels. Performance evidence for the shared CRIF vectorized static
RiskType path is recorded in
[docs/performance/frtb-common-crif-normalizer-report.md](../../performance/frtb-common-crif-normalizer-report.md).
