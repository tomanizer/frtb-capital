# Time-series, shock, scenario-vector, and surface metadata

`frtb-result-store` persists run-scoped analytical metadata for completed FRTB
runs. These artifacts let the Capital Navigator inspect evidence behind a
stored result without making the frontend, capital kernels, or result store own
market-data lifecycle, shock generation, or surface interpolation.

This document is the practical developer guide. The boundary decisions are in:

- [ADR 0049](../../decisions/0049-result-evidence-and-market-data-platform-boundary.md):
  result evidence versus market/scenario-data platforms;
- [ADR 0050](../../decisions/0050-risk-factor-identity-and-package-projection-boundary.md):
  risk-factor identity and package projections;
- [ADR 0051](../../decisions/0051-rfet-observation-and-vendor-mapping-evidence-boundary.md):
  RFET observation and vendor/internal mapping evidence;
- [ADR 0052](../../decisions/0052-organisation-hierarchy-and-regime-assignment-boundary.md):
  organisation hierarchy and regime assignment.

## What is implemented now

The current implementation provides four common artifact families:

| Family | Schema id | Artifact type | Current purpose |
| --- | --- | --- | --- |
| Time series | `common.time_series.v1` | `TIME_SERIES` | RFET observation timelines, PLAT/backtesting vectors, UPL placeholders, and similar run-scoped timelines. |
| Shock definitions | `common.shock_definition.v1` | `SHOCK_DEFINITION` | Persisted shock definitions such as SBM curvature up/down shocks. |
| Scenario vectors | `common.scenario_vector_metadata.v1` | `SCENARIO_VECTOR_METADATA` | Metadata for scenario sets/vectors that link dense IMA arrays to ids, dates, labels, and source rows. |
| Surface grids | `common.surface_grid.v1` | `SURFACE_GRID` | Two-axis surface or grid points such as option tenor by underlying tenor. |

Each family supports:

- registered Arrow schema validation;
- deterministic artifact ids;
- semantic partition metadata;
- available/no-data/unsupported availability states;
- paged detail reads through the optional FastAPI app;
- lineage links through ordinary result-store `LineageRef` rows.

## What this is not

These artifacts are evidence/read-model contracts only. They do not:

- source market data;
- collect vendor observations;
- calibrate curves or volatility surfaces;
- interpolate or extrapolate surfaces;
- generate shock sets or stress scenarios;
- calculate or restate capital;
- infer RFET, PLAT, backtesting, SBM, or CVA classifications in the frontend.

Packages compute regulatory meaning. The result store persists and serves the
evidence. The Navigator displays it.

## Artifact rows

### Time series

`common.time_series.v1` rows identify one observed or calculated timeline.

Typical fields:

- `run_id`;
- `time_series_id`;
- `observation_date`;
- `value_name`;
- `value`;
- optional `currency`;
- optional `risk_factor_id`;
- optional `scenario_id`;
- optional `mapping_version`;
- `source_row_id`.

Use this schema for small run-scoped timelines and fixture-backed vectors. Do
not use it as a long-history market-data warehouse. RFET, PLAT, UPL, and
backtesting behavior needs semantic profiles before those rows drive regulatory
status or UI warnings.

### Shock definitions

`common.shock_definition.v1` rows identify persisted shocks.

Typical fields:

- `run_id`;
- `shock_id`;
- `shock_direction`;
- `shock_type`;
- `magnitude`;
- `unit`;
- optional `risk_factor_id`;
- optional `scenario_id`;
- optional `mapping_version`;
- optional `regulatory_rule_id`;
- `source_row_id`.

Single `shock_id` rows are sufficient for simple evidence display. Multi-factor
or regulatory-behavior shock workflows need a future shock-set semantic profile
with `shock_set_id` or explicit affected `risk_factor_id` membership.

### Scenario-vector metadata

`common.scenario_vector_metadata.v1` rows link scenario-vector evidence to
scenario ids and dates.

Typical fields:

- `run_id`;
- `scenario_set_id`;
- `scenario_vector_id`;
- `scenario_id`;
- `observation_date`;
- `scenario_label`;
- optional `mapping_version`;
- `source_row_id`.

Dense scenario arrays remain package-owned or artifact-backed. The metadata
rows are for discovery, lineage, display, and drill-through.

### Surface grids

`common.surface_grid.v1` rows identify two-axis surface points.

Typical fields:

- `run_id`;
- `surface_id`;
- `surface_point_id`;
- `axis_1_name`;
- `axis_1_value`;
- `axis_2_name`;
- `axis_2_value`;
- `value_name`;
- `value`;
- `unit`;
- optional `risk_factor_id`;
- optional `mapping_version`;
- `source_row_id`.

Surface axes are stored coordinates, not interpolation instructions. The suite
may store an upstream interpolation policy identifier in future semantic
profiles, but it does not implement interpolation or calibration here.

## Availability states

Artifact refs may be available or intentionally unavailable:

| Status | Meaning | UI behavior |
| --- | --- | --- |
| `AVAILABLE` | Rows or references are present for the committed run. | Fetch paged detail rows. |
| `NO_DATA` | The run explicitly lacks this dataset. | Render an honest no-data state. |
| `UNSUPPORTED` | The package/profile does not implement this dataset. | Render a capability-boundary state, not an empty result. |

Unavailable refs use `row_count=0`, `format="none"`, and status-specific URIs.
They may still carry semantic partition values, so clients can route through the
same detail endpoints and receive `mode=artifact_unavailable`.

## API endpoints

List endpoints return full artifact refs, compact catalog rows, and status
counts. Detail endpoints return paged rows or an unavailable-artifact payload.

```text
GET /runs/{run_id}/time-series
GET /runs/{run_id}/time-series/{time_series_id}/points
GET /runs/{run_id}/shocks
GET /runs/{run_id}/shocks/{shock_id}
GET /runs/{run_id}/scenario-vectors
GET /runs/{run_id}/scenario-vectors/{scenario_vector_id}/metadata
GET /runs/{run_id}/surfaces
GET /runs/{run_id}/surfaces/{surface_id}/slice
```

Surface slices accept optional `axis_1_value` and `axis_2_value` filters.
Paged payloads expose `row_count`, `filtered_row_count`, `returned`,
`next_offset`, and `rows`.

## Navigator flow

The Navigator should:

1. Load a run.
2. Load the capital tree.
3. Load metadata catalogs.
4. On selected row, load node lineage.
5. Match lineage `source_id` values to metadata catalog `artifact_id` values.
6. Render only the contextual metadata tabs linked to the selected row.

Catalog `artifact_id` values identify stored artifact refs, while detail routes
usually use semantic partition ids such as `time_series_id`, `shock_id`,
`scenario_vector_id`, or `surface_id`.

The Navigator must not display all metadata families globally for every row.
The selected capital row determines which evidence is relevant.

## Current fixture examples

The Capital Navigator fixture includes:

- `ts-rfet-usd-5y`: available RFET observation time series;
- `ts-plat-upl`: no-data UPL time series;
- `shock-sbm-curvature-up` and `shock-sbm-curvature-down`;
- `scenario-vector-rtpl`;
- `surface-usd-swaption-vol`;
- `surface-cva-full-vol-cube`: unsupported CVA surface cube;
- unsupported CRIF drill-through refs.

These examples are synthetic. They exercise the storage/API/UI contract, not
final regulatory data coverage.

## Current limitations and next slices

The implementation intentionally does not yet provide:

- `RiskFactorId` / `RiskFactorSetId` value objects;
- a run-scoped risk-factor catalog;
- referential validation from artifact `risk_factor_id` values to that catalog;
- RFET vendor/internal mapping diagnostics;
- shock-set membership and calibration metadata;
- surface convention/interpolation-policy semantic profiles;
- PLAT/UPL semantic profiles with spike diagnostics;
- organisation hierarchy/regime assignment APIs beyond existing result-store
  hierarchy primitives.

Those are follow-up slices guided by ADRs 0049-0052.
