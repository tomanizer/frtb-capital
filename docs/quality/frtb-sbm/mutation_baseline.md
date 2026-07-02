# SBM Mutation Testing Baseline

Date: 2026-07-02

Issue: #1149, parent epic #1150

## Scope

Mutation testing is configured for the SBM calculation boundary:

- `packages/frtb-sbm/src/frtb_sbm/capital.py`
- `packages/frtb-sbm/src/frtb_sbm/curvature.py`
- `packages/frtb-sbm/src/frtb_sbm/weighted_sensitivity.py`

The package-local `mutmut` configuration lives in
`packages/frtb-sbm/pyproject.toml`. The root `make mutation-sbm` target runs the
package-local configuration with `HYPOTHESIS_PROFILE=dev` and preloads NumPy
before invoking mutmut, matching the IMA target's in-process NumPy reload
workaround.

Mutation is intentionally excluded for adapter, batch handoff, audit,
reference-data, and support-matrix surfaces. This baseline is for sensitivity
weighting, curvature, and public SBM capital assembly, not IO or serialization
plumbing.

## Command

```sh
make mutation-sbm
```

## Baseline Result

Tool: `mutmut` 3.5.0

Baseline command completed successfully on 2026-07-02.

| Metric | Count |
| --- | ---: |
| Total mutants | 960 |
| Killed | 753 |
| Survived | 207 |
| Timeout | 0 |
| No tests | 0 |
| Skipped | 0 |
| Suspicious | 0 |
| Segfault | 0 |

Killed-only mutation score: `78.44%`.

The initial SBM mutation floor is set to this honest baseline in
`docs/quality/package_maturity.toml`. The score establishes mutation-testing
evidence for SBM; follow-up hardening should raise the floor rather than lower
or re-scope this baseline.

## Module Breakdown

| Module | Total | Killed | Survived | Score |
| --- | ---: | ---: | ---: | ---: |
| `capital.py` | 343 | 274 | 69 | 79.88% |
| `curvature.py` | 439 | 335 | 104 | 76.31% |
| `weighted_sensitivity.py` | 178 | 144 | 34 | 80.90% |

## Schedule

Mutation testing is not part of the normal push gate because it is slower than
the deterministic package suite. `.github/workflows/mutation.yml` runs it
weekly, exports `mutmut-cicd-stats.json`, and enforces this killed-only
baseline with `scripts/ci/check_mutation_score.py`. It should also be rerun for
material changes to the configured SBM calculation boundary.
