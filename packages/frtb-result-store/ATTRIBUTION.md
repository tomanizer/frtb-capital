# Capital Attribution

`frtb-result-store` persists attribution evidence. It does not calculate
capital, choose attribution methods, or reinterpret package contribution
records.

## Current Support

The storage model `CapitalAttributionRecord` is compatible with
`frtb_common.CapitalContribution` and can be built with:

```python
CapitalAttributionRecord.from_contribution(...)
```

The record supports:

- Euler contribution rows;
- residual rows;
- unsupported attribution rows;
- target type/id overrides for dashboard and drillthrough views;
- optional artifact references and metadata.

Persisted mart/API projections expose producer-owned attribution rows for
analysts:

- `top_contributors`;
- `residual_attribution`;
- `unsupported_attribution`;
- `DuckDbParquetResultStore.top_contributors(...)`;
- `DuckDbParquetResultStore.residual_attribution_records(...)`;
- `DuckDbParquetResultStore.unsupported_attribution_records(...)`;
- `GET /runs/{run_id}/top-contributors`;
- `GET /runs/{run_id}/attribution/residual`;
- `GET /runs/{run_id}/attribution/unsupported`.

Projection rows include `contribution`, `residual`, `method`, `source_id`,
`source_level`, `target_id`, and `unsupported_reason` for drillthrough. The
result store does not create those values; it only materializes and serves them.

## Method

Storage preserves the method supplied by the component package:

- `ANALYTICAL_EULER` records must include `marginal_multiplier` and
  `contribution`.
- `RESIDUAL` and `UNSUPPORTED` records from the shared contribution DTO carry
  their explanatory text in `reason`; the storage row mirrors that text into
  its store-local `unsupported_reason` field for query convenience.

The package validates row shape, registered target/source types, finite numeric
fields, and append-only run identity. It does not validate that a whole set of
records reconciles to capital; that remains the responsibility of the producing
package and orchestration bundle contracts.

## Inputs Used

Storage consumes:

- run id and graph node id;
- a shared `CapitalContribution` record;
- optional target type/id;
- optional artifact id;
- optional metadata.

## Allocation Grain

The result store accepts the source grain supplied by the producer, subject to
registered attribution target-type validation. Typical grains include desk,
sensitivity, net JTD, bucket, category, component, and suite.

## Limitations

- No capital formulae are implemented here.
- No Euler, residual, or unsupported-method decisions are made here.
- Marts and APIs are storage-only projections over `CapitalAttributionRecord`;
  they must not implement finite differences, standalone attribution, or Euler
  fallback logic.
- Corrections require a new append-only run bundle; existing evidence is not
  mutated.
- Capital packages must not import `frtb-result-store`.

## Evidence

Relevant tests live under:

- `packages/frtb-result-store/tests`

Design references:

- `docs/decisions/0012-capital-impact-attribution.md`
- `docs/decisions/0038-suite-wide-attribution-impact-contract.md`
