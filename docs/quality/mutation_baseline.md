# Mutation Testing Baseline

Date: 2026-05-28

Issue: #12, audit issue #11

## Scope

Mutation testing is configured for the FRTB-IMA calculation modules:

- `packages/frtb-ima/src/frtb_ima/expected_shortfall.py`
- `packages/frtb-ima/src/frtb_ima/liquidity_horizon.py`
- `packages/frtb-ima/src/frtb_ima/imcc.py`
- `packages/frtb-ima/src/frtb_ima/nmrf.py`
- `packages/frtb-ima/src/frtb_ima/pla.py`
- `packages/frtb-ima/src/frtb_ima/capital.py`
- `packages/frtb-ima/src/frtb_ima/reduced_set.py`

The mutmut configuration lives in `packages/frtb-ima/pyproject.toml` so mutant
module names match package-local imports such as `frtb_ima.expected_shortfall`.
The root `make mutation` target runs that package-local configuration.

Mutation is intentionally excluded for non-calculation support modules:

- `src/frtb_ima/demo_data.py`
- `src/frtb_ima/audit.py`
- `src/frtb_ima/logging.py`

## Command

```sh
make mutation
```

The Makefile target sets `FRTB_IMA_MUTATION_IMPORT=1` and
`HYPOTHESIS_PROFILE=dev`, then preloads NumPy before invoking mutmut. The preload
avoids a NumPy extension reload failure in mutmut's in-process pytest runner.

## Baseline Result

Tool: `mutmut` 3.5.0

Baseline command completed successfully on 2026-05-28.

| Metric | Count |
| --- | ---: |
| Total mutants | 1,881 |
| Killed | 1,413 |
| Survived | 467 |
| Timeout | 1 |
| No tests | 0 |
| Skipped | 0 |
| Suspicious | 0 |

Killed-only mutation score: `75.12%`.

Detected mutation score, counting the timeout as detected but not killed:
`75.17%`.

The project quality target for this slice is a killed-only score of at least
`75%` across the configured calculation modules. The 2026-05-28 baseline meets
that target without excluding any survivor from the denominator.

## Module Breakdown

| Module | Total | Killed | Survived | Timeout | Score |
| --- | ---: | ---: | ---: | ---: | ---: |
| `capital.py` | 227 | 163 | 63 | 1 | 71.81% |
| `expected_shortfall.py` | 93 | 81 | 12 | 0 | 87.10% |
| `imcc.py` | 209 | 164 | 45 | 0 | 78.47% |
| `liquidity_horizon.py` | 135 | 106 | 29 | 0 | 78.52% |
| `nmrf.py` | 404 | 314 | 90 | 0 | 77.72% |
| `pla.py` | 472 | 349 | 123 | 0 | 73.94% |
| `reduced_set.py` | 341 | 236 | 105 | 0 | 69.21% |

The aggregate target is met. `capital.py`, `pla.py`, and `reduced_set.py` are
the main hardening targets for future mutation-score increases.

## Schedule

Mutation testing is not part of the PR push gate because it is slower than the
normal suite. `.github/workflows/mutation.yml` runs it weekly and also supports
manual dispatch.
