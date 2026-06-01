# Performance Benchmarks

This directory records suite-level benchmark baselines that are intentionally
separate from the normal `make check` gate.

## FRTB-IMA Target Scale

Run the current benchmark from the workspace root:

```bash
make benchmark
```

The benchmark exercises deterministic synthetic inputs at the target scale named
in `packages/frtb-ima/CLAUDE.md`: 10,000 scenarios, five liquidity-horizon
subsets, five risk classes, and 100 desks. It covers nested liquidity-horizon
vector construction, LHA ES, IMCC decomposition, NMRF SES aggregation,
PLA/backtesting aggregate checks, desk capital assembly, audit-record
construction, and NDJSON serialisation.

The local target writes `dist/benchmarks/frtb-ima-target-scale.json`. A scheduled
GitHub Actions workflow also runs the same target weekly and uploads the JSON
report as an artifact; it is not a pull-request gate.

`frtb-ima-target-scale-baseline.json` is a point-in-time baseline. It is not an
SLA. Use it to spot order-of-magnitude regressions and refresh it when hardware,
Python, NumPy, or benchmark dimensions change.

## FRTB-SBM Batch and Arrow Handoffs

Run the SBM handoff benchmark from the workspace root:

```bash
uv run python benchmarks/sbm_adapter_harness.py
```

The benchmark compares row-compatibility paths with migrated Arrow/batch paths
for GIRR vega, FX delta, equity delta, commodity delta, CSR non-sec delta, CSR
sec non-CTP delta, CSR sec CTP delta, and GIRR curvature validation. It records
whether accepted-row `SbmSensitivity` dataclasses were materialized, splits
handoff/batch/calculation timings, checks row/batch capital reconciliation for
capital-producing paths, and keeps pairwise evidence in summary mode.

`frtb-sbm-batch-arrow-report.md` contains the human-readable report.
`frtb-sbm-batch-arrow-baseline.json` is the checked-in baseline for
order-of-magnitude regression review.

## Common CRIF Normalizer

Run the CRIF normalizer benchmark from the workspace root:

```bash
uv run python benchmarks/crif_normalizer_harness.py
```

The benchmark compares the callback-compatible row path with the vectorized
static RiskType mapping path in `frtb_common.crif`. It also verifies that the
SBM GIRR delta CRIF consumer still builds an `SbmSensitivityBatch` without
accepted-row `SbmSensitivity` dataclasses.

`frtb-common-crif-normalizer-report.md` contains the human-readable report.
`frtb-common-crif-normalizer-baseline.json` is the checked-in synthetic
baseline for order-of-magnitude regression review.
