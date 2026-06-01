# FRTB IMA Arrow Handoff Triage

Issue: #319
Parent: #312
Architecture: [ADR 0023](../decisions/0023-arrow-tabular-handoff-boundary.md)

## Boundary

IMA scenario P&L values remain dense NumPy arrays. Expected shortfall,
liquidity-horizon adjustment, IMCC, stress-period selection, PLA, backtesting,
and NMRF numerical kernels do not accept Arrow, pandas, or Polars objects.

Arrow is used where IMA inputs are naturally tabular and lineage-heavy:

- capital-run input manifests;
- scenario-axis metadata;
- RFET real-price observation evidence.

The adapter path is:

```text
upstream table or file
    -> pyarrow-backed normalized handoff
    -> IMA-owned immutable metadata/evidence batch
    -> NumPy-native calculation or existing audit result records
```

## Delivered Path

The #319 implementation adds:

- `normalize_ima_scenario_metadata_arrow_table`
- `build_scenario_metadata_batch_from_handoff`
- `ScenarioMetadataBatch`
- `normalize_ima_rfet_observation_arrow_table`
- `build_rfet_observation_batch_from_handoff`
- `RFETObservationBatch`
- `assess_rfet_observation_batch`

`ScenarioMetadataBatch` validates scenario ids, dates, scenario-set labels,
provenance JSON, source-row lineage, source hashes, and handoff hashes without
constructing one `ScenarioMetadata` object per accepted row. `to_metadata()`
exists only as a compatibility bridge for current APIs.

`RFETObservationBatch` carries accepted real-price observations as immutable
NumPy columns. `assess_rfet_observation_batch` mirrors the existing RFET
decision logic but does not construct accepted `RealPriceObservation` objects.
It materializes excluded observations only because the existing audit result
records exclusion details.

## Not Changed

- Scenario-cube and scenario-vector values are not moved into Arrow.
- IMA formula kernels are not rewritten as dataframe expressions.
- Existing row/dataclass APIs remain available for compatibility and audit
  comparison.

## Validation

Package tests cover:

- handoff alias normalization for scenario and RFET tables;
- dictionary/chunked text columns;
- source hash, handoff hash, and batch input hash propagation;
- optional-column defaults;
- scenario metadata compatibility materialization;
- RFET batch assessment equivalence with the existing row/dataclass path.
