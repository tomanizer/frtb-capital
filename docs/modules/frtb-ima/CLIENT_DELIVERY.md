# frtb-ima client delivery guide

This guide defines how clients deliver IMA inputs to `frtb_ima`. IMA has two
separate delivery channels: dense NumPy scenario artifacts for capital kernels
and Arrow tabular handoffs for lineage-heavy metadata and RFET evidence.

This package is not approved for regulatory reporting. Regulatory citations
point to proposed U.S. NPR 2.0, Basel FRTB, and EU/PRA comparison material;
supervisory approval, validation, and production governance remain outside this
package.

## Delivery channels

| Channel | Format | Purpose |
| --- | --- | --- |
| Scenario cube | NumPy `.npz` artifacts / `ScenarioCube` arrays | ES, LHA, IMCC, NMRF, PLA, and backtesting numerical kernels. |
| Tabular handoff | Arrow tables matching IMA handoff specs | Scenario metadata, RFET observations, and capital-run input manifest lineage. |

Do not put scenario P&L vectors into Arrow handoff for capital kernels. Scenario
vectors remain dense NumPy arrays so expected shortfall, liquidity-horizon
adjustment, IMCC, NMRF, PLA, and backtesting kernels stay NumPy-native.

## Stable tabular symbols

| Handoff | Spec | Normalize | Build / assess | Notes |
| --- | --- | --- | --- | --- |
| Scenario metadata | `IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS` | `normalize_ima_scenario_metadata_arrow_table` | `build_scenario_metadata_batch_from_arrow`, `ScenarioMetadataBatch`, `input_hash_for_scenario_metadata_batch` | Describes scenario ids, dates, sets, calibration windows, provenance, and row lineage. |
| RFET observations | `IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS` | `normalize_ima_rfet_observation_arrow_table` | `build_rfet_observation_batch_from_arrow`, `assess_rfet_observation_batch`, `RFETObservationBatch`, `input_hash_for_rfet_observation_batch` | High-volume RFET evidence path without accepted-row `RealPriceObservation` materialization. |
| Input manifest | `IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS` | `normalize_ima_input_manifest_arrow_table` | `build_capital_run_input_manifest_from_arrow`, `CapitalRunInputManifest` | Names NPZ, CSV, evidence, and audit artifacts with source system, checksum, record count, vector count, and validation status. |

`ScenarioMetadataBatch.to_metadata()` is a compatibility bridge for existing
APIs and tests. It is not the production hot path for high-volume metadata.

## Row vs batch RFET

| Path | Input | Entry point | Use |
| --- | --- | --- | --- |
| Row path | `RealPriceObservation` dataclasses | `assess_rfet_evidence` | Compatibility, notebooks, and small evidence sets. |
| Batch path | `RFETObservationBatch` from Arrow handoff | `assess_rfet_observation_batch` | Recommended high-volume RFET evidence path. |

The batch path preserves the same RFET decision semantics while avoiding one
accepted `RealPriceObservation` dataclass per row on the hot path. It may still
materialize excluded observation records because existing audit results include
exclusion details.

## Canonical integration fixture

The committed integration example is
[`packages/frtb-ima/tests/fixtures/capital_run_v1/`](../../../packages/frtb-ima/tests/fixtures/capital_run_v1/).
It includes:

| Artifact | Purpose |
| --- | --- |
| `scenario_cube.npz` | Dense scenario P&L vectors. |
| `stress_histories.npz`, `stress_history_metadata.csv` | Stress-period calibration inputs. |
| `rfet_observations.csv`, `nmrf_evidence.json`, `nmrf_artifacts.npz` | RFET and NMRF evidence artifacts. |
| `scenario_metadata.csv`, `risk_factors.csv`, `params.json` | Scenario and risk-factor lineage. |
| `manifest.json`, `expected_outputs.json` | Replay contract and deterministic expected outputs. |

Clients should mirror the artifact naming, checksum, and row-count discipline in
the fixture when preparing onboarding packs.

## Upstream responsibilities

The following remain upstream responsibilities:

- market-data sourcing and real-price observation collection;
- trade pricing and revaluation;
- dense scenario P&L generation;
- NMRF pricing and valuation artifacts;
- risk-factor taxonomy and trade classification governance;
- business calendar governance and stress-period candidate evidence;
- PLA and backtesting vector production before package metrics are calculated.

## References

- [`docs/performance/frtb-ima-arrow-handoff-triage.md`](../../performance/frtb-ima-arrow-handoff-triage.md)
- [`docs/decisions/0023-arrow-tabular-handoff-boundary.md`](../../decisions/0023-arrow-tabular-handoff-boundary.md)
- [`docs/decisions/0011-core-runtime-dependency-policy.md`](../../decisions/0011-core-runtime-dependency-policy.md)
- [`packages/frtb-ima/docs/DATASET_CONTRACT.md`](../../../packages/frtb-ima/docs/DATASET_CONTRACT.md)
