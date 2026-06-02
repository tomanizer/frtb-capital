# FRTB-SBM Batch and Arrow Performance Report

This report is the point-in-time evidence pack for the SBM Arrow/batch migration
tracked by #270 and completed by #285, #286, #287, #288, #289, and #290.

The benchmark harness is `benchmarks/sbm_adapter_harness.py`. It builds
deterministic synthetic portfolios, runs the row-compatibility path and the
Arrow/batch path for each migrated SBM area, checks that capital-producing paths
match the row result, and records timing and evidence counters. The checked-in
baseline JSON is `frtb-sbm-batch-arrow-baseline.json`.

Run it from the workspace root:

```bash
uv run python benchmarks/sbm_adapter_harness.py \
  --row-count 720 \
  --output dist/benchmarks/frtb-sbm-batch-arrow.json
```

## Baseline

Baseline generated: 2026-06-01T06:54:12.206389+00:00.

Environment: macOS-26.5 arm64, Python 3.11.15. The baseline uses the
`BASEL_MAR21` profile, synthetic data only, and `SUMMARY` pairwise evidence mode.
Memory values in the JSON use `tracemalloc` as a Python-allocation proxy; Arrow
and NumPy native buffers may not be fully counted.

| Case | Rows | Factors | Row path total ms | Arrow/batch total ms | Row dataclasses | Arrow accepted-row dataclasses | Pairwise records total | Pairwise materialized |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GIRR vega | 720 | 60 | 1485 | 1368 | 720 | 0 | 260280 | 0 |
| FX delta | 720 | 6 | 109 | 96 | 720 | 0 | 130680 | 0 |
| Equity delta | 720 | 720 | 395 | 357 | 720 | 0 | 125280 | 0 |
| Commodity delta | 720 | 60 | 396 | 344 | 720 | 0 | 156600 | 0 |
| CSR non-sec delta | 720 | 720 | 556 | 552 | 720 | 0 | 156600 | 0 |
| CSR sec non-CTP delta | 720 | 720 | 339 | 377 | 720 | 0 | 125280 | 0 |
| CSR sec CTP delta | 720 | 720 | 268 | 271 | 720 | 0 | 156600 | 0 |
| GIRR curvature validation | 720 | 15 | 19 | 77 | 720 | 0 | 0 | 0 |

The totals are useful for order-of-magnitude regression checks, not as an SLA.
The JSON records the timing split for table construction, handoff normalization,
batch construction, capital calculation, audit serialization, and curvature
branch selection.

The JSON also contains a `summary` block for budget checks and agent triage. It
aggregates raw rows, netted factor counts, pairwise evidence counts, accepted-row
dataclass materialization, peak traced memory, split timing groups, and stable
result/audit hashes. The `wall_clock_proxy` sums measured Arrow/batch path
timings only. The `phase_probes` block records the GIRR delta weighting-input
construction, netting/factor-grid correlation matrix, and scenario-correlation
adjustment timings as supplemental breakdowns because the full batch compute
timer already includes that work.

## Conclusions

The migrated high-volume paths do not create one accepted `SbmSensitivity`
dataclass per input row. The row-compatibility path still exists and still
materializes row dataclasses; the Arrow/batch path records zero accepted-row
dataclasses for every migrated case.

The capital-producing Arrow/batch paths reconcile against the row path within
the harness before a report is emitted. The original #270 baseline covered GIRR
vega, FX delta, equity delta, commodity delta, CSR non-sec delta, CSR sec
non-CTP delta, CSR sec CTP delta, and a GIRR curvature validation probe. Later
SBM vectorisation work extended the supported high-volume matrix to delta,
vega, and curvature across all seven BASEL_MAR21 SBM risk classes; use the
support matrix in
[`packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md`](../../packages/frtb-sbm/docs/REGULATORY_TRACEABILITY.md)
as the current source of truth.

Pairwise evidence is summarized, not materialized, in the benchmark controls.
The baseline therefore exercises portfolios with more than 100,000 pairwise
relationships per migrated capital path without storing every correlation
record in the audit payload.

The remaining visible cost is package batch construction and row-equivalent
input hashing. That cost is deliberate for deterministic lineage, replay, and
audit compatibility. If future larger runs show batch construction dominating,
the next performance task should target vectorized hashing and canonical string
normalization rather than reintroducing per-row dataclass materialization.

## Issue #315 Conversion Check

After the Arrow conversion-copy reduction in #315, the 720-row local SBM
benchmark on macOS-26.5 arm64 / Python 3.11.15 recorded a `wall_clock_proxy` of
3.417s against the checked-in 3.442s baseline, with the validation/batch-build
summary dropping from 0.485s to 0.335s. Accepted-row dataclass materialization
remained zero on the Arrow/batch path.

Batch construction improved for each benchmarked handoff path:

| Case | #315 batch build ms | Baseline batch build ms |
| --- | ---: | ---: |
| GIRR vega | 41 | 64 |
| FX delta | 45 | 51 |
| Equity delta | 38 | 52 |
| Commodity delta | 38 | 67 |
| CSR non-sec delta | 38 | 63 |
| CSR sec non-CTP delta | 38 | 59 |
| CSR sec CTP delta | 40 | 56 |
| GIRR curvature validation | 49 | 64 |

## Supported High-Volume Entrypoints

Use the public Arrow normalizers and handoff/batch entrypoints in
`frtb_sbm.arrow_handoff` for migrated high-volume inputs. The supported
BASEL_MAR21 capital handoffs cover delta, vega, and curvature for GIRR, FX,
equity, commodity, CSR non-sec, CSR sec non-CTP, and CSR sec CTP. The portfolio
dispatcher accepts multiple normalized handoffs and groups them by
`(risk_class, risk_measure)` before aggregation.

Unsupported paths remain explicit boundaries: unsupported regulatory profiles,
equity repo vega/curvature sub-features, missing CTP decomposition evidence,
and broader CRIF-to-Arrow coverage outside the implemented GIRR delta CRIF
mapping.
