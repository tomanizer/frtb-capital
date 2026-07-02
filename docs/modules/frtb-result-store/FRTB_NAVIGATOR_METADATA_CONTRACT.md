# FRTB Navigator metadata contract

This contract defines how the FRTB Navigator should consume time-series,
shock, scenario-vector, and surface metadata from `frtb-result-store`.

It is a read-model contract. The Navigator must not fetch raw object-store files
directly, infer missing regulatory classifications, interpolate surfaces,
generate shocks, or calculate capital.

## Visual posture

Use the existing approved FRTB Navigator direction:

- light high-density workbench;
- fixed zero-scroll zones;
- thin rules, compact rows, monospace numerics;
- one blue selection accent;
- no hero cards, shadows, gradients, or duplicated facts.

Metadata views belong in the lower audit inspector, driven by the selected
blotter row and its lineage. They should be compact tables first; sparklines or
small plots are acceptable only when they preserve row-level auditability.

## Endpoint families

All endpoint families expose a list route with full artifact refs and a compact
`catalog` array. Use the catalog for selectors, badges, and empty-state routing.
Use detail endpoints for rows.

| Family | List endpoint | Detail endpoint |
| --- | --- | --- |
| Time series | `GET /runs/{run_id}/time-series` | `GET /runs/{run_id}/time-series/{time_series_id}/points` |
| Shocks | `GET /runs/{run_id}/shocks` | `GET /runs/{run_id}/shocks/{shock_id}` |
| Scenario vectors | `GET /runs/{run_id}/scenario-vectors` | `GET /runs/{run_id}/scenario-vectors/{scenario_set_id}/{scenario_vector_id}/metadata` |
| Surfaces | `GET /runs/{run_id}/surfaces` | `GET /runs/{run_id}/surfaces/{surface_id}/slice` |

Catalog rows include:

- `artifact_id`;
- `artifact_type`;
- `component`;
- `artifact_status`;
- `status_reason`;
- `navigator_role`;
- `row_count`;
- `partition_values`.

## Selection flow

1. Load the selected run.
2. Load the capital tree and the metadata catalogs.
3. When a blotter row is selected, call
   `GET /runs/{run_id}/nodes/{node_id}/lineage`.
4. Match lineage `source_id` values to catalog `artifact_id` values.
5. Render contextual inspector tabs only for linked metadata families.

For example:

- `ima-rates-desk` links to the IMA P&L vector, RFET observation timeline, and
  IMA scenario vector.
- `sbm-girr-usd` links to SBM sensitivities, curvature up/down shocks, and the
  USD swaption volatility surface.

Do not display all metadata tabs globally. The selected row determines which
metadata exists at that altitude.

## Availability states

`artifact_status=AVAILABLE` means the detail endpoint can return persisted rows.

`artifact_status=NO_DATA` means the run explicitly lacks that dataset. The
detail endpoint should return `mode=artifact_unavailable`, empty rows,
`artifact_status`, `status_reason`, and zeroed reconciliation counters.

`artifact_status=UNSUPPORTED` means the dataset is outside the implemented
package/profile scope. Render this differently from no data: unsupported is a
capability boundary, not an empty result. Unsupported detail payloads also use
`mode=artifact_unavailable` and zeroed reconciliation counters.

Unavailable metadata refs can still carry semantic `partition_values`; for
example a missing UPL vector can be selected as `time_series_id=ts-plat-upl`.
The Navigator should use the semantic route and render the returned unavailable
payload rather than treating it as a missing route.
Blank or missing semantic partition values are invalid store data. The UI should
not synthesize fallback selector labels for such refs; the result store rejects
them before manifest commit.

## Detail reconciliation

Paged detail payloads expose:

- committed artifact `row_count`;
- query-specific `filtered_row_count`;
- page `returned`;
- `next_offset`;
- `rows`.

The inspector must display these counters in its audit strip. A filtered surface
slice may have `row_count=2`, `filtered_row_count=1`, and `returned=1`; that is
not a reconciliation failure.

## Fixture-backed examples

The FRTB Navigator fixture currently provides:

- `ts-rfet-usd-5y` as an available RFET observation time series;
- `ts-plat-upl` as a no-data UPL time series;
- `shock-sbm-curvature-up` and `shock-sbm-curvature-down`;
- `scenario-vector-rtpl`;
- `surface-usd-swaption-vol`;
- `surface-cva-full-vol-cube` as an unsupported CVA surface cube.

The fixture also exposes unsupported CRIF drillthrough through an unavailable
artifact ref. UI code must never fake CRIF rows.

## Cache and cancellation keys

Use these cache keys:

- catalog: `runId:metadata-family`;
- node lineage: `runId:nodeId:lineage`;
- detail: `runId:metadata-family:semantic-id:filters:offset:limit`;
- surface slice: `runId:surfaceId:axis1:axis2:offset:limit`.

Changing run, selected row, metadata family, semantic id, surface axis filter,
or page offset must abort the previous in-flight detail request.

## No client-owned semantics

The Navigator may display metadata fields but must not reinterpret them:

- `mapping_version` is provenance, not a client-side mapping switch;
- `regulatory_rule_id` is displayed as evidence, not as a rule engine input;
- `shock_direction` and `shock_type` are persisted definitions, not generated
  from UI controls;
- surface axes are stored coordinates, not interpolation instructions.

The broader developer guide to these artifact families is
[`ARTIFACT_METADATA.md`](ARTIFACT_METADATA.md). The architectural boundaries for
future risk-factor catalogs, RFET vendor mapping, and organisation hierarchy are
recorded in ADRs 0049-0052.
