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
