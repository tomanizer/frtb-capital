# Common CRIF Normalizer Performance Report

This report is the point-in-time evidence pack for #284. It compares the
existing callback-compatible CRIF normalization path with the vectorized
static RiskType mapping path added for package adapters that provide
`CrifRiskTypeMapping` tables.

Run it from the workspace root:

```bash
uv run python benchmarks/crif_normalizer_harness.py \
  --row-count 20000 \
  --output dist/benchmarks/frtb-common-crif-normalizer.json
```

The checked-in baseline JSON is
`frtb-common-crif-normalizer-baseline.json`.

## Baseline

Baseline generated: 2026-06-01T04:14:15.866362+00:00.

Environment: macOS-26.5 arm64, Python 3.11.15. The baseline uses 20,000
synthetic GIRR delta CRIF-like rows. It produced 19,642 accepted rows and 358
rejected rows.

| Path | Seconds | Python peak bytes | Accepted-row dataclasses |
| --- | ---: | ---: | ---: |
| Row compatibility normalizer | 3.834 | 16,317,444 | n/a |
| Vectorized static mapping normalizer | 0.051 | 2,404,025 | 0 |
| SBM GIRR delta CRIF-to-batch consumer | 1.470 | 49,764,237 | 0 |

On this baseline, the vectorized common path is about 75.1x faster than the row
compatibility normalizer and uses about 6.8x less traced Python allocation.

## Interpretation

The benchmark uses a deterministic synthetic GIRR delta CRIF-like Arrow table.
It intentionally includes accepted rows, unsupported RiskType rows, non-finite
amount rows, and blank source row ids. The harness asserts that accepted rows,
rejected rows, diagnostics, and source hashes match between the row
compatibility path and vectorized static-mapping path before it emits a report.

The benchmark also feeds the same table through the public SBM GIRR delta CRIF
handoff and then into `build_girr_delta_batch_from_handoff`. That records zero
accepted-row `SbmSensitivity` dataclasses on the high-volume handoff path.

The JSON report records wall-clock seconds and `tracemalloc` peak bytes for the
row compatibility path, the vectorized common path, and the SBM batch consumer.
The timings are useful for order-of-magnitude regression checks, not as an SLA.
