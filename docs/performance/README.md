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

## FRTB-IMA Arrow Handoffs

Run the IMA Arrow batch benchmark from the workspace root:

```bash
make ima-arrow-handoff-benchmark
```

The benchmark covers the Arrow -> normalized handoff -> immutable batch path for
scenario metadata and RFET real-price observations. It records parse, adapt,
build, and RFET assessment timings, compares RFET row and batch assessment
hashes, and hard-gates accepted-row dataclass materialization at zero on the
Arrow fast path.

## FRTB-SBM Batch and Arrow Handoffs

Run the SBM handoff benchmark from the workspace root:

```bash
make sbm-benchmark
```

The benchmark compares row-compatibility paths with migrated Arrow/batch paths
for GIRR vega, FX delta, equity delta, commodity delta, CSR non-sec delta, CSR
sec non-CTP delta, CSR sec CTP delta, and GIRR curvature validation. It records
whether accepted-row `SbmSensitivity` dataclasses were materialized, splits
handoff/batch/calculation timings, checks row/batch capital reconciliation for
capital-producing paths, and keeps pairwise evidence in summary mode. Its
machine-readable `summary` block aggregates ingestion, validation, weighting,
audit serialization, supplemental netting/factor-grid and correlation/scenario
phase probes, plus raw rows, netted factors, pairwise counts, dataclass counts,
peak traced memory, and stable result/audit hashes. The `wall_clock_proxy`
sums the measured Arrow/batch path timings only; phase-probe timings are
reported separately because the full batch compute timer already includes that
work.

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

## Arrow Package Batch Rollout

`arrow-package-rollout.md` is the suite-level coordination note for the DRC,
RRAO, and CVA rollout under issue #271. It links the child package issues and
PRs, points to each triage artifact, identifies the public high-volume batch
entrypoints, and records the closure checks that keep package kernels out of
dataframe expression layers.

## FRTB-DRC Arrow Batch Triage

`frtb-drc-arrow-batch-triage.md` documents the DRC data-shape and hotspot
assessment for the package-owned Arrow batch -> NumPy batch -> kernel path.
It now covers non-securitisation, securitisation non-CTP, and CTP fast paths,
and explains why DRC keeps regulatory netting inside package NumPy code instead
of moving regulatory calculations into a dataframe expression layer.

Run the DRC row-vs-Arrow benchmark from the workspace root:

```bash
make drc-benchmark
```

The command writes `dist/benchmarks/frtb-drc-batch-arrow.json` and compares
row-compatible `DrcPosition` processing with class-specific Arrow batch ->
`DrcPositionBatch` paths for deterministic synthetic non-securitisation,
securitisation non-CTP, and CTP inputs.
The default PR-scale benchmark uses 500 rows and 100 issuer/group identities;
larger exploratory runs can pass `--row-count` and `--issuer-count` directly to
`benchmarks/drc_adapter_harness.py`.

## FRTB-RRAO Arrow Batch Triage

`frtb-rrao-arrow-batch-triage.md` documents the RRAO residual-risk data-shape
and hotspot assessment for the package-owned Arrow batch -> NumPy batch ->
line-kernel path. It covers flat evidence columns for exotic, other residual
risk, supervisor-directed, exclusion, back-to-back, and investment-fund rows,
and it defines opaque nested payloads as fail-closed inputs.

## FRTB-CVA Arrow Batch Triage

`frtb-cva-arrow-batch-triage.md` documents the CVA counterparty, netting-set,
hedge, and SA-CVA sensitivity data-shape assessment for the package-owned Arrow
handoff -> NumPy batch -> kernel path. It covers BA-CVA aggregation, hedge
recognition, SA-CVA weighted-sensitivity grouping, qualified-index metadata, and
why dataframe expression kernels are not the regulatory calculation boundary.

Run the CVA target-scale benchmark from the workspace root:

```bash
make cva-benchmark
```

The command writes `dist/benchmarks/frtb-cva-target-scale.json` and covers BA-CVA
counterparty/netting-set Arrow batches plus SA-CVA sensitivity Arrow batches.
It exposes parse, adapt, build, calculate, memory, accepted-row dataclass, and
row-vs-Arrow payload-hash equivalence metrics for budget checks.
