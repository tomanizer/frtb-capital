# Benchmark profile and regression budgets

This note records the 2026-05-31 audit benchmark snapshot and the regression
budgets used by `scripts/ci/check_benchmark_budgets.py`.

## Commands

```bash
make benchmark              # IMA target-scale JSON -> dist/benchmarks/frtb-ima-target-scale.json
make sbm-benchmark          # SBM Arrow/batch JSON -> dist/benchmarks/frtb-sbm-batch-arrow.json
make rrao-benchmark         # RRAO target-scale JSON -> dist/benchmarks/frtb-rrao-target-scale.json
make benchmark-budget-check # compare artifacts to docs/quality/benchmark_budgets.toml
```

Benchmark budget checks are **manual/local by default**. They are not part of
the standard PR CI matrix because wall-clock timings vary across developer
hardware and GitHub-hosted runners. Run them before performance-sensitive
changes or when investigating regressions.

## Audit snapshot (2026-05-31)

| Benchmark | Wall clock | Dominant phase | Notes |
| --- | --- | --- | --- |
| IMA target-scale | ~73.9 s | `imcc_decomposition` ~54.2 s | 10k scenarios, 100 desks |
| SBM Arrow/batch | ~3.3 s wall-clock proxy | migrated batch capital calculations | 5,760 synthetic rows across migrated paths, zero accepted-row dataclasses, 1,111,320 pairwise relationships summarized |
| RRAO target-scale | ~45.2 s | validation/classification/allocation | 100k positions, ~3,024 positions/s, ~402 MB peak traced memory |

The SBM benchmark uses the checked-in
[`frtb-sbm-batch-arrow-baseline.json`](../performance/frtb-sbm-batch-arrow-baseline.json)
as the stable baseline for budget checks. The budget is deliberately tolerance
based: the current generated artifact is compared to the baseline wall-clock
proxy with a multiplier, while exact structural controls such as accepted-row
dataclass materialization remain hard maximums.

## Next optimization targets

### IMA — IMCC decomposition

Profiling from the target-scale benchmark shows `imcc_decomposition` dominates
wall clock. Likely contributors:

- repeated sorting and expected-shortfall passes over nested liquidity-horizon
  vectors;
- per-desk recomputation where vector reuse is possible;
- allocation churn when assembling IMCC breakdown structures.

Prefer preserving deterministic audit outputs and explicit branch metadata over
micro-optimizations that obscure regulatory flow.

### RRAO — validation and audit payload construction

At 100k positions, validation/classification and audit serialization contribute
materially after the core capital sum. Opportunities:

- reduce repeated field validation on homogeneous position batches;
- stream or defer verbose audit payload assembly when run controls allow;
- keep ordering and replay hashes stable when optimizing.

## Budget file

Thresholds live in [`benchmark_budgets.toml`](benchmark_budgets.toml). Update
that file when a deliberate optimization lands and the new baseline is measured
on representative hardware.

When refreshing a baseline, run the benchmark command, inspect the split metrics
for ingestion, validation, weighting, netting/factor-grid, correlation/scenario,
and audit serialization, then update both the checked-in baseline and any
tolerance in `benchmark_budgets.toml` in the same PR. Do not tighten or loosen a
budget without preserving the generated artifact that justifies it.
