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

## Observed run

Local run from this worktree on 2026-05-29:

| Field | Value |
| --- | ---: |
| Python | 3.11.14 |
| Platform | macOS-13.7.8-x86_64-i386-64bit |
| Positions | 100,000 |
| Build positions | 5.280 seconds |
| Calculate | 54.232 seconds |
| Serialize | 22.042 seconds |
| Wall time | 81.713 seconds |
| Calculate throughput | 1,843.9 positions/second |
| Peak traced memory | 412,352,265 bytes |
| Total RRAO | 155,470,000.0 |
| Payload hash | `c60490c0e675561c878aea716e20ce78add011737dc32986ae3d9bfec0053add` |
| Ordering hash | `1e6b188a7d2a6fee31654e9d5b1e929268ab3ec78c9e99aedc6401b6710df3ee` |

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
