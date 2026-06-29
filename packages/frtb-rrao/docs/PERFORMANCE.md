# RRAO performance and replay controls

This document records engineering controls for `frtb-rrao` target-scale replay.
It is not a regulatory validation report and must not be used as final capital
evidence.

## Target benchmark

Run the target-scale benchmark with:

```bash
make rrao-benchmark
```

The command writes `dist/benchmarks/frtb-rrao-target-scale.json` and prints the
same JSON report. The default deterministic fixture contains:

- 100,000 synthetic RRAO positions;
- 50 desks and 10 legal entities;
- U.S. NPR 2.0 profile canonical inputs;
- 80,000 included lines and 20,000 listed-exclusion lines;
- no dataframe runtime dependency.

The benchmark report includes wall-clock phase timings, peak traced memory, the
RRAO input/profile hashes, input-hash algorithm labels, a stable serialized
audit payload hash, and a stable line-ordering hash. Row/dataclass ingress is
reported as two phases:
`row_adapter_seconds` / `row_batch_build_seconds` for canonical dataclass
validation, projection, batch validation, and input hashing; and
`row_kernel_seconds` for `calculate_rrao_capital_from_batch` on the resulting
canonical batch.

## Ingress guidance

Use column or Arrow ingress for target-scale books and production-like handoff
tests. Those paths avoid constructing `RraoPosition` dataclasses for every row
and go directly into the package-owned canonical batch before the single RRAO
kernel. Row/dataclass ingress remains useful for tests, notebooks, fixtures, and
small books where ergonomic construction and public API compatibility are more
important than high-volume adapter throughput.

All ingress paths converge on `calculate_rrao_capital_from_batch`; the row path
does not have a separate capital formula or row kernel.

## Observed runs

Local benchmark observations from this worktree on 2026-06-29 after the row
adapter/kernel timing split, row adapter copy-elision, vectorized canonical
batch validation reuse, and Arrow columnar v2 input hashing:

| Field | Value |
| --- | ---: |
| Benchmark id | `frtb-rrao-target-scale-v2` |
| Python | 3.11.14 |
| Platform | macOS-13.7.8-x86_64-i386-64bit |
| Positions | 100,000 |
| Row build positions | 8.789 seconds |
| Row adapter / batch build | 26.648 seconds |
| Row kernel | 9.795 seconds |
| Row serialize | 0.982 seconds |
| Row adapter throughput | 3,753 positions/second |
| Row kernel throughput | 10,209 positions/second |
| Batch build columns | 2.410 seconds |
| Batch build/validate/hash | 24.534 seconds |
| Batch calculate | 9.833 seconds |
| Batch serialize | 1.053 seconds |
| Batch calculate throughput | 10,170 positions/second |
| Arrow table build | 0.098 seconds |
| Arrow batch build/validate/hash | 4.784 seconds |
| Arrow calculate | 10.603 seconds |
| Arrow calculate throughput | 9,431 positions/second |
| Peak traced memory | 551,210,668 bytes |
| Total RRAO | 155,470,000.0 |
| Batch total delta | 0.0 |
| Arrow total delta | 0.0 |
| Row input hash algorithm | `json-row-v1` |
| Arrow input hash algorithm | `arrow-columnar-v2` |
| Payload hash | `e56b615706fff279739e8fcb98453efe75cb3175030c722879992ff5a9804ddc` |
| Batch payload hash | `e56b615706fff279739e8fcb98453efe75cb3175030c722879992ff5a9804ddc` |
| Arrow payload hash | `cc5ad7153b6fbe35ed02f9d2b2b34914e39f3b0ee56e063da73f076f3860f951` |
| Ordering hash | `1e6b188a7d2a6fee31654e9d5b1e929268ab3ec78c9e99aedc6401b6710df3ee` |
| Input hash | `fb63ed0fb27d0134c3ad9812da579b375bfc10c63520a91a550bf101943d8dbf` |
| Arrow input hash | `dd2a157c721ffdf9008c0465a8c9d6bd990b25d086cc13b5016556672a1e7540` |

The column-batch payload hash matches the row path because the benchmark
provides the same lineage source-column map. The Arrow batch has a distinct
payload and input hash because the flat handoff does not carry that tuple-valued
lineage map and now uses `arrow-columnar-v2` instead of the row JSON hash. It
preserves capital, line ordering, and zero capital delta. The row adapter timing
includes dataclass validation, projection, canonical batch validation, and input
hashing; it does not include the row kernel timing.

Local benchmark observations from this worktree on 2026-05-29:

| Field | Value |
| --- | ---: |
| Python | 3.11.14 |
| Platform | macOS-13.7.8-x86_64-i386-64bit |
| Positions | 100,000 |
| Baseline build positions | 5.629 seconds |
| Baseline calculate | 56.720 seconds |
| Baseline serialize | 21.300 seconds |
| Baseline wall time | 83.930 seconds |
| Baseline throughput | 1,763 positions/second |
| Optimized build positions | 5.629 seconds |
| Optimized calculate | 19.422 seconds |
| Optimized serialize | 0.673 seconds |
| Optimized wall time | 25.877 seconds |
| Optimized throughput | 5,148.8 positions/second |
| Peak traced memory | 408,897,609 bytes |
| Total RRAO | 155,470,000.0 |
| Payload hash | `c60490c0e675561c878aea716e20ce78add011737dc32986ae3d9bfec0053add` |
| Ordering hash | `1e6b188a7d2a6fee31654e9d5b1e929268ab3ec78c9e99aedc6401b6710df3ee` |
| Input hash | `fb63ed0fb27d0134c3ad9812da579b375bfc10c63520a91a550bf101943d8dbf` |

The optimization removed repeated validation between public assembly,
classification, line-building, and input hashing. It also replaced generic
recursive dataclass normalization in the audit path with explicit serializers
for the RRAO dataclasses. Under the deterministic 100k fixture,
calculate-plus-serialize time dropped from roughly 78.0 seconds to roughly 20.1
seconds while preserving payload and ordering hashes.

Treat these numbers as a baseline observation, not a pass/fail threshold.
Future performance changes should explain large timing or memory drift under
the same deterministic fixture.

## Replay hashes

Replay tests hash the deterministic JSON serialization with sorted keys and
compact separators. They also hash result line ordering separately. These
controls are designed to detect:

- output ordering drift;
- numeric contribution drift;
- profile or input hash changes;
- accidental fixture or serialization changes.

Changing any hash intentionally requires updating the relevant fixture or
performance documentation in the same PR.
