# RRAO Mutation Testing Baseline

Date: 2026-05-29

Issues: #119, #122

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

Baseline command completed successfully on 2026-05-29.

| Metric | Count |
| --- | ---: |
| Total mutants | 1,266 |
| Killed | 1,082 |
| Survived | 184 |
| Timeout | 0 |
| No tests | 0 |
| Skipped | 0 |
| Suspicious | 0 |

Killed-only mutation score: `85.47%`.

The IMA precedent recorded in
`docs/quality/frtb-ima/mutation_baseline.md` is `75.12%`. RRAO therefore
exceeds the suite precedent across the configured v1 boundary without excluding
any survivor from the denominator.

## Module Breakdown

| Module | Total | Killed | Survived | Score |
| --- | ---: | ---: | ---: | ---: |
| `audit.py` | 273 | 212 | 61 | 77.66% |
| `capital.py` | 141 | 138 | 3 | 97.87% |
| `classification.py` | 134 | 119 | 15 | 88.81% |
| `validation.py` | 718 | 613 | 105 | 85.38% |

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
