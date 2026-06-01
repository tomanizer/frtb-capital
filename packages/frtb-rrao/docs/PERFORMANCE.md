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
RRAO input/profile hashes, a stable serialized audit payload hash, and a stable
line-ordering hash.

## Observed runs

Local benchmark observations from this worktree on 2026-06-01 after the RRAO
batch decision-vectorization work:

| Field | Value |
| --- | ---: |
| Benchmark id | `frtb-rrao-target-scale-v2` |
| Python | 3.11.15 |
| Platform | macOS-26.5-arm64-arm-64bit |
| Positions | 100,000 |
| Row build positions | 3.464 seconds |
| Row calculate | 10.731 seconds |
| Row serialize | 0.497 seconds |
| Row calculate throughput | 9,319 positions/second |
| Batch build columns | 0.940 seconds |
| Batch build/validate/hash | 25.061 seconds |
| Batch calculate | 3.522 seconds |
| Batch serialize | 0.662 seconds |
| Batch calculate throughput | 28,393 positions/second |
| Arrow table build | 0.052 seconds |
| Arrow handoff build/validate/hash | 30.787 seconds |
| Arrow calculate | 3.820 seconds |
| Arrow calculate throughput | 26,177 positions/second |
| Peak traced memory | 847,075,379 bytes |
| Total RRAO | 155,470,000.0 |
| Batch total delta | 0.0 |
| Arrow total delta | 0.0 |
| Batch accepted row dataclasses | 0 |
| Arrow accepted row dataclasses | 0 |
| Payload hash | `c60490c0e675561c878aea716e20ce78add011737dc32986ae3d9bfec0053add` |
| Batch payload hash | `c60490c0e675561c878aea716e20ce78add011737dc32986ae3d9bfec0053add` |
| Arrow payload hash | `21afd04a1351c99a2adc19d0df115ce54c21b978978cc8872d0ded0ad59de427` |
| Ordering hash | `1e6b188a7d2a6fee31654e9d5b1e929268ab3ec78c9e99aedc6401b6710df3ee` |
| Input hash | `fb63ed0fb27d0134c3ad9812da579b375bfc10c63520a91a550bf101943d8dbf` |

The column-batch payload hash matches the row path because the benchmark
provides the same lineage source-column map. The Arrow handoff has a distinct
payload hash because the flat handoff does not carry that tuple-valued lineage
map, but it preserves capital, line ordering, and zero accepted-row dataclass
materialization.

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
