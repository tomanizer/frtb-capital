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

Baseline generated: 2026-06-01T06:45:21.509726+00:00.

Environment: macOS-26.5 arm64, Python 3.11.15. The baseline uses the
`BASEL_MAR21` profile, synthetic data only, and `SUMMARY` pairwise evidence mode.
Memory values in the JSON use `tracemalloc` as a Python-allocation proxy; Arrow
and NumPy native buffers may not be fully counted.

| Case | Rows | Factors | Row path total ms | Arrow/batch total ms | Row dataclasses | Arrow accepted-row dataclasses | Pairwise records total | Pairwise materialized |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GIRR vega | 720 | 60 | 1366 | 1241 | 720 | 0 | 260280 | 0 |
| FX delta | 720 | 6 | 123 | 104 | 720 | 0 | 130680 | 0 |
| Equity delta | 720 | 720 | 388 | 357 | 720 | 0 | 125280 | 0 |
| Commodity delta | 720 | 60 | 346 | 325 | 720 | 0 | 156600 | 0 |
| CSR non-sec delta | 720 | 720 | 570 | 530 | 720 | 0 | 156600 | 0 |
| CSR sec non-CTP delta | 720 | 720 | 329 | 347 | 720 | 0 | 125280 | 0 |
| CSR sec CTP delta | 720 | 720 | 259 | 268 | 720 | 0 | 156600 | 0 |
| GIRR curvature validation | 720 | 15 | 19 | 73 | 720 | 0 | 0 | 0 |

The totals are useful for order-of-magnitude regression checks, not as an SLA.
The JSON records the timing split for table construction, handoff normalization,
batch construction, capital calculation, audit serialization, and curvature
branch selection.

The JSON also contains a `summary` block for budget checks and agent triage. It
aggregates raw rows, netted factor counts, pairwise evidence counts, accepted-row
dataclass materialization, peak traced memory, non-overlapping split timing groups, and stable
result/audit hashes. The `phase_probes` block records the GIRR delta
weighting-input construction, netting/factor-grid correlation matrix, and
scenario-correlation adjustment timings separately from ingestion and audit
serialization.

## Conclusions

The migrated high-volume paths do not create one accepted `SbmSensitivity`
dataclass per input row. The row-compatibility path still exists and still
materializes row dataclasses; the Arrow/batch path records zero accepted-row
dataclasses for every migrated case.

The capital-producing Arrow/batch paths reconcile against the row path within
the harness before a report is emitted. This covers GIRR vega, FX delta, equity
delta, commodity delta, CSR non-sec delta, CSR sec non-CTP delta, and CSR sec
CTP delta. GIRR curvature is validation-only: the harness verifies row and
batch branch selection, but public curvature capital remains fail-closed until
the cited curvature aggregation path is implemented.

Pairwise evidence is summarized, not materialized, in the benchmark controls.
The baseline therefore exercises portfolios with more than 100,000 pairwise
relationships per migrated capital path without storing every correlation
record in the audit payload.

The remaining visible cost is package batch construction and row-equivalent
input hashing. That cost is deliberate for deterministic lineage, replay, and
audit compatibility. If future larger runs show batch construction dominating,
the next performance task should target vectorized hashing and canonical string
normalization rather than reintroducing per-row dataclass materialization.

## Supported High-Volume Entrypoints

Use the public Arrow normalizers and handoff/batch entrypoints in
`frtb_sbm.arrow_handoff` for migrated high-volume inputs. The supported capital
handoffs are GIRR delta, GIRR vega, FX delta, equity delta, commodity delta, CSR
non-sec delta, CSR sec non-CTP delta, and CSR sec CTP delta. The supported
validation-only handoff is GIRR curvature.

Unsupported paths remain explicit boundaries: curvature capital, FX/equity/
commodity/CSR vega, non-GIRR curvature, unsupported regulatory profiles, and
broader CRIF coverage outside the implemented GIRR delta CRIF mapping.
