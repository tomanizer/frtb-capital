# RRAO Mutation Testing Baseline

Date: 2026-07-02

Issues: #119, #122, #1146

## Scope

Mutation testing is configured for the RRAO v1 calculation and validation
boundary:

- `packages/frtb-rrao/src/frtb_rrao/audit.py`
- `packages/frtb-rrao/src/frtb_rrao/capital.py`
- `packages/frtb-rrao/src/frtb_rrao/classification.py`
- `packages/frtb-rrao/src/frtb_rrao/validation.py`

The package-local `mutmut` configuration lives in
`packages/frtb-rrao/pyproject.toml`. The root `make mutation-rrao` target runs
the package-local configuration with `HYPOTHESIS_PROFILE=dev`.

## Command

```sh
make mutation-rrao
```

## Baseline Result

Tool: `mutmut` 3.5.0

Baseline command completed successfully on 2026-07-02.

| Metric | Count |
| --- | ---: |
| Total mutants | 420 |
| Killed | 396 |
| Survived | 14 |
| Timeout | 10 |
| No tests | 0 |
| Skipped | 0 |
| Suspicious | 0 |

Killed-only mutation score: `94.29%`.

The RRAO quality floor is now `94.29%`, matching the 2026-07-02 baseline
without excluding any survivor from the denominator. Timeout-classified mutants
are reported separately and are not counted as survivors by `mutmut`'s exported
CI stats.

## Module Breakdown

| Module | Total | Killed | Survived | Timeout | Score |
| --- | ---: | ---: | ---: | ---: | ---: |
| `audit.py` | 251 | 236 | 5 | 10 | 94.02% |
| `capital.py` | 79 | 79 | 0 | 0 | 100.00% |
| `classification.py` | 90 | 81 | 9 | 0 | 90.00% |

## Property Tests

The same quality slice added Hypothesis tests under
`packages/frtb-rrao/tests/test_properties.py` covering:

- additive total equals the sum of included-line add-ons;
- explicit excluded positions do not change total RRAO;
- input permutation is stable after canonical sorting;
- distinct canonical inputs produce distinct input hashes;
- included and excluded line partitions are disjoint.

## Schedule

Mutation testing is not part of the normal push gate because it is slower than
the deterministic package suite. `.github/workflows/mutation.yml` runs it
weekly, exports `mutmut-cicd-stats.json`, and enforces this killed-only
baseline with `scripts/ci/check_mutation_score.py`. It should also be rerun for
material changes to `audit.py`, `capital.py`, `classification.py`, or
`validation.py`, and at least before a release candidate that changes RRAO
capital behavior.
